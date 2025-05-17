import copy
import json
import logging
import sys
import yaml

import asyncio

import kopf
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

LABELS = {
    "domain": "toletum.org",
    "version": "v1",
    "name": "mongodaemon",
    "manifest": "ds_manifest.yaml",
    "operator": "mongodaemons.toletum.org",
    "mongodb_node": "mongo-toletum-org-mongodb",
    "daemonset_status": "mongodaemons.toletum.org.status",
    "primary_label": "mongo-toletum-org-primary",
    "disabled_label": "mongo-toletum-org-disabled"
}

logger = logging.getLogger(LABELS['operator'])
logging.basicConfig(level=logging.INFO)


# Cargar configuración K8s
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()


def storage(patch, cluster_status: dict):
    patch.metadata.annotations.update({LABELS["daemonset_status"]: json.dumps(cluster_status)})


def run_rs_initiate(pod_name, namespace, members):
    api = client.CoreV1Api()
    rs_members = [f'{{_id: {i}, host: "{host}"}}' for i, host in enumerate(members)]
    rs_initiate = f'rs.initiate({{_id: "rs0", members: [{", ".join(rs_members)}]}})'

    cmd = ["mongosh", "--eval", rs_initiate]

    resp = stream(api.connect_get_namespaced_pod_exec,
                  pod_name,
                  namespace,
                  command=cmd,
                  stderr=True, stdin=False,
                  stdout=True, tty=False,
                  _request_timeout=10)
    return resp.strip()


def isPrimary(pod_name, namespace):
    api = client.CoreV1Api()
    cmd = ["mongosh", "--eval", 'db.hello().isWritablePrimary']
    try:
        resp = stream(api.connect_get_namespaced_pod_exec,
                      pod_name,
                      namespace,
                      command=cmd,
                      stderr=True, stdin=False,
                      stdout=True, tty=False,
                      _request_timeout=10).strip().lower()
        # Poner "true"/"false" como string
        label_value = "true" if resp == "true" else "false"
        body = {"metadata": {"labels": {LABELS['primary_label']: label_value}}}
        api.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
        return True if resp == "true" else False
    except Exception as ex:
        body = {"metadata": {"labels": {LABELS['disabled_label']: "true"}}}
        api.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
        return None

def create_admin_user(pod_name, namespace, user, password):
    api = client.CoreV1Api()
    create_user_cmd = f'db.getSiblingDB("admin").createUser({{user:"{user}", pwd:"{password}", roles:[{{role:"root", db:"admin"}}]}})'
    cmd = ["mongosh", "--eval", create_user_cmd]
    resp = stream(api.connect_get_namespaced_pod_exec,
                  pod_name,
                  namespace,
                  command=cmd,
                  stderr=True, stdin=False,
                  stdout=True, tty=False,
                  _request_timeout=10).strip().lower()
    return resp


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
    logger.info("Nodes: %s", [n.metadata.name for n in nodes.items])


@kopf.on.create(LABELS['domain'], LABELS['version'], LABELS['name'])
def create_ds(spec, name, namespace, patch, **kwargs):
    api = client.AppsV1Api()
    COapi = client.CustomObjectsApi()

    # Listar BusyboxDaemon en el namespace
    objs = COapi.list_namespaced_custom_object(
        group="toletum.org", version="v1",
        namespace=namespace, plural="mongodaemons")

    members = spec.get("members", [])
    keyfile = spec.get("keyfile", "")

    if len(members) < 3:
        raise kopf.PermanentError("Se requieren al menos 3 miembros para el replicaset.")

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
    cluster_status = {
        "created": True,
        "ready": False,
        "replicaSet": False,
        "user": False
    }
    storage(patch, cluster_status)


@kopf.on.delete(LABELS['domain'], LABELS['version'], LABELS['name'])
def delete_ds(name, namespace, patch, **kwargs):
    api = client.AppsV1Api()
    try:
        api.delete_namespaced_daemon_set(name=name, namespace=namespace)
        logger.info(f"DaemonSet {name} eliminado de {namespace}")
        cluster_status = {
            "created": False,
            "ready": False,
            "replicaSet": False,
            "user": False
        }
        storage(patch, cluster_status)
    except ApiException as e:
        if e.status == 404:
            logger.info(f"DaemonSet {name} not found, deleted before")
        else:
            raise


@kopf.daemon(LABELS['domain'], LABELS['version'], LABELS['name'], timeout=60)
async def watch_cluster(spec, name, namespace, patch, stopped, **kwargs):
    v1 = client.CoreV1Api()
    while not stopped:
        try:
            annotations = kwargs.get('body', {}).get('metadata', {}).get('annotations', {})
            cluster_status = json.loads(annotations.get(LABELS["daemonset_status"]))
        except Exception as ex:
            cluster_status = {}

        label_selector = f"app={LABELS['mongodb_node']}"
        pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        c = 0
        pod_ready = None
        pod_primary = None
        for pod in pods.items:
            ispri = None
            if cluster_status['replicaSet']:
               ispri = isPrimary(pod.metadata.name, namespace)
            estado = {
                "pod": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": all([c.ready for c in (pod.status.container_statuses or [])]),
                "isPrimary": ispri
            }
            logger.info("Pods status for %s: %s", name, estado)
            if ispri:
                pod_primary = pod.metadata.name
            if estado.get('ready'):
                pod_ready = estado.get('pod')
                c += 1

        cluster_status["ready"] = len(pods.items) == c

        if cluster_status.get('replicaSet', False) and not cluster_status.get('user', False) and pod_primary is not None:
            try:
                user = spec.get("user", "")
                password = spec.get("password", "")
                status = create_admin_user(pod_primary, namespace, user, password)
                logger.info("CREATED ROOT USER: %s", status)
                cluster_status['user'] = True
                storage(patch, cluster_status)
            except Exception as ex:
                logger.error("CREATING ROOT USER: %s", user)

        # Ready and not replicaSet
        if  cluster_status.get('ready', False) and not cluster_status.get('replicaSet', False):
            members = spec.get("members", [])
            logger.info("replicaSet config... %s", str(members))
            try:
                status = run_rs_initiate(pod_ready, namespace, members)
                if status == '{ ok: 1 }':
                    cluster_status['replicaSet'] = True
                    storage(patch, cluster_status)
                    logger.info("replicaSet ready")
                elif status == 'MongoServerError: already initialized':
                    logger.warning("replicaSet: already initialized")
                    cluster_status['replicaSet'] = True
                    storage(patch, cluster_status)
                else:
                    logger.error("replicaSet: %s", status)
            except Exception as ex:
                logger.error("replicaSet Exception: %s", str(ex))

        logger.info("%s/%s daemonset_status: %s", namespace, name, str(cluster_status))
        await asyncio.sleep(10)
