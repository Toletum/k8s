import copy
import sys
import yaml

import asyncio

import kopf
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from helpers import run_rs_initiate, isPrimary, create_admin_user, generate_keyfile
from consts import LABELS, logger

cluster_status = {
    'ready': False,
    'replicaSet': False,
    'userCreate': False
}


# Cargar configuración K8s
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    v1 = client.CoreV1Api()
    logger.info("Checking node availability...")
    label_selector = f"{LABELS['mongodb_node']}=true"
    nodes = v1.list_node(label_selector=label_selector)
    num_nodes = len(nodes.items)
    if num_nodes < 3:
        logger.error(f"At least 3 nodes with the label {label_selector} are required")
        logger.error(" -> kubectl label node <NODE> mongo-toletum-org-mongodb=true --overwrite")
        sys.exit(1)

    cluster_nodes = [
        {"name": node.metadata.name, "ip": addr.address}
        for node in nodes.items
        for addr in node.status.addresses
        if addr.type == "InternalIP"
    ]

    logger.info("%s", str(cluster_nodes))


@kopf.on.create(LABELS['domain'], LABELS['version'], LABELS['name'])
def create_ds(spec, name, namespace, patch, **kwargs):
    api = client.AppsV1Api()
    COapi = client.CustomObjectsApi()

    # Listar BusyboxDaemon en el namespace
    objs = COapi.list_namespaced_custom_object(
        group="toletum.org", version="v1",
        namespace=namespace, plural="mongodaemons")

    keyfile = generate_keyfile()

    # Si ya hay otro distinto a este, abortar
    for obj in objs.get('items', []):
        if obj['metadata']['name'] != name:
            raise kopf.PermanentError("Solo se permite un Mongodaemons por namespace")

    with open(LABELS['manifest']) as f:
        template = yaml.safe_load(f)

    ds_manifest = copy.deepcopy(template)
    ds_manifest["metadata"]["name"] = name
    cmd_init = f"echo '{keyfile}' > /data/db/keyfile && chmod 400 /data/db/keyfile && chown 999:999 -R /data/db"
    ds_manifest["spec"]["template"]["spec"]["initContainers"][0]["command"][-1] = cmd_init

    api.create_namespaced_daemon_set(namespace=namespace, body=ds_manifest)

@kopf.on.delete(LABELS['domain'], LABELS['version'], LABELS['name'])
def delete_ds(name, namespace, patch, **kwargs):
    api = client.AppsV1Api()
    try:
        api.delete_namespaced_daemon_set(name=name, namespace=namespace)
        logger.info(f"DaemonSet {namespace} - {name} deleted ")
    except ApiException as e:
        if e.status == 404:
            logger.info(f"DaemonSet {namespace} - {name} not found, deleted before")
        else:
            raise


@kopf.daemon(LABELS['domain'], LABELS['version'], LABELS['name'], timeout=60)
async def watch_cluster(spec, name, namespace, patch, stopped, **kwargs):
    global cluster_status

    core = client.CoreV1Api()
    while not stopped:
        label_selector = f"app={LABELS['mongodb_node']}"
        pods = core.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        c = 0
        pod_ready = None
        pod_primary = None
        for pod in pods.items:
            ispri = None
            pod_status = {
                "pod": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": all([c.ready for c in (pod.status.container_statuses or [])])
            }
            if pod_status['ready']:
                ispri = isPrimary(pod.metadata.name, namespace)
                pod_status['isPrimary'] = ispri

            logger.info("Pods status for %s: %s", name, pod_status)
            if ispri:
                pod_primary = pod.metadata.name
            if pod_status.get('ready'):
                pod_ready = pod_status.get('pod')
                c += 1

        cluster_status['ready'] = 1 <= c == len(pods.items)

        if cluster_status['ready'] and not cluster_status['replicaSet'] and pod_ready:
            try:
                response = run_rs_initiate(pod_ready, namespace, pods.items)
                if response == '{ ok: 1 }':
                    logger.info("replicaSet ready")
                    cluster_status['replicaSet'] = True
                elif response == 'MongoServerError: already initialized':
                    logger.warning("replicaSet: already initialized")
                    cluster_status['replicaSet'] = True
                elif response == 'MongoServerError: Command replSetInitiate requires authentication':
                    logger.warning("replicaSet: User already created before")
                    cluster_status['replicaSet'] = True
                else:
                    cluster_status['replicaSet'] = False
                    logger.error("replicaSet: %s", response)
            except Exception as ex:
                logger.error("replicaSet Exception: %s", str(ex))

        if cluster_status['replicaSet'] and not cluster_status['userCreate'] and pod_primary:
            try:
                adminuser = spec.get("adminuser", {})
                user = adminuser.get("user", "")
                password = adminuser.get("password", "")
                status = create_admin_user(pod_primary, namespace, user, password)
                if status == 'mongoservererror: command createuser requires authentication':
                    logger.warning("User already created before")
                else:
                    logger.info("Root user %s created:: %s", user, status)
                cluster_status['userCreate'] = True
            except Exception as ex:
                logger.error("CREATING ROOT USER: %s", user)

        logger.info("%s/%s cluster_status: %s", namespace, name, str(cluster_status))

        if cluster_status['userCreate']:
            sleep = 60
        else:
            sleep = 5

        await asyncio.sleep(sleep)
