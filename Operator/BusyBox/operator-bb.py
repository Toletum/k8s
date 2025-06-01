import asyncio
import copy
import json
import logging
import sys

import kopf
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

LABELS = {
    "domain": "toletum.org",
    "version": "v1",
    "name": "busyboxdaemon",
    "operator": "busyboxdaemons.toletum.org",
    "mongodb_node": "mongo-toletum-org-mongodb",
    "daemonset_status": "busyboxdaemons.toletum.org.status"
}

cluster_nodes = []

logger = logging.getLogger(LABELS['operator'])
logging.basicConfig(level=logging.INFO)


# Cargar configuración K8s
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    global cluster_nodes

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
def create_ds(name, namespace, patch, **kwargs):
    api = client.AppsV1Api()
    COapi = client.CustomObjectsApi()

    # Listar BusyboxDaemon en el namespace
    objs = COapi.list_namespaced_custom_object(
        group="toletum.org", version="v1",
        namespace=namespace, plural="busyboxdaemons")

    # Si ya hay otro distinto a este, abortar
    for obj in objs.get('items', []):
        if obj['metadata']['name'] != name:
            raise kopf.PermanentError("Solo se permite un BusyboxDaemon por namespace")

    with open('operator-bb.manifest') as f:
        template = yaml.safe_load(f)

    ds_manifest = copy.deepcopy(template)
    ds_manifest['metadata']['name'] = name
    ds_manifest['metadata']['labels']['app'] = name
    ds_manifest['spec']['selector']['matchLabels']['app'] = name
    ds_manifest['spec']['template']['metadata']['labels']['app'] = name

    api.create_namespaced_daemon_set(namespace=namespace, body=ds_manifest)
    patch.metadata.annotations.update({LABELS["daemonset_status"]: json.dumps({
        "created": True,
    })})


@kopf.on.delete(LABELS['domain'], LABELS['version'], LABELS['name'])
def delete_ds(name, namespace, patch, **kwargs):
    api = client.AppsV1Api()
    try:
        api.delete_namespaced_daemon_set(name=name, namespace=namespace)
        logger.info(f"DaemonSet {name} eliminado de {namespace}")
        patch.metadata.annotations.update({LABELS["daemonset_status"]: json.dumps({
            "created": False,
        })})
    except ApiException as e:
        if e.status == 404:
            logger.info(f"DaemonSet {name} not found, deleted before")
        else:
            raise


@kopf.daemon(LABELS['domain'], LABELS['version'], LABELS['name'], timeout=60)
async def watch_cluster(spec, name, namespace, patch, stopped, **kwargs):
    global cluster_nodes

    logger.info("%s", str(cluster_nodes))
    v1 = client.CoreV1Api()
    while not stopped:
        label_selector = f"app={name}"

        pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
        for pod in pods.items:
            estado = {
                "pod": pod.metadata.name,
                "phase": pod.status.phase,
                "ready": all([c.ready for c in (pod.status.container_statuses or [])])
            }
            logger.info("Pods status for %s: %s", name, estado)

        annotations = kwargs.get('body', {}).get('metadata', {}).get('annotations', {})
        try:
            cluster_status = json.loads(annotations.get(LABELS["daemonset_status"]))
        except Exception as ex:
            cluster_status = {}

        logger.info("%s/%s daemonset_status: %s", namespace, name, str(cluster_status))
        await asyncio.sleep(10)
