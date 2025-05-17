import copy
import json
import logging
import sys

import kopf
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger("busyboxdaemons.toletum.org")
logging.basicConfig(level=logging.INFO)

# Cargar configuración K8s
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    v1 = client.CoreV1Api()
    logger.info("Checking node availability...")
    nodes = v1.list_node(label_selector="mongo-toletum-org-mongodb=true")
    num_nodes = len(nodes.items)
    if num_nodes < 3:
        logger.error("At least 3 nodes with the label mongo-toletum-org-mongodb=true are required")
        logger.error(" -> kubectl label node <NODE> mongo-toletum-org-mongodb=true --overwrite")
        sys.exit(1)
    logger.info("Nodes: %s", [n.metadata.name for n in nodes.items])

@kopf.on.create('toletum.org', 'v1', 'busyboxdaemon')
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
    patch.metadata.annotations.update({'busyboxdaemons.toletum.org.status': json.dumps({
        "replicaSet": False,
        "user": False
    })})


@kopf.on.delete('toletum.org', 'v1', 'busyboxdaemon')
def delete_ds(name, namespace, patch, **kwargs):
    api = client.AppsV1Api()
    try:
        api.delete_namespaced_daemon_set(name=name, namespace=namespace)
        logger.info(f"DaemonSet {name} eliminado de {namespace}")
        patch.metadata.annotations.update({'busyboxdaemons.toletum.org.status': json.dumps({
            "replicaSet": False,
            "user": False
        })})
    except ApiException as e:
        if e.status == 404:
            logger.info(f"DaemonSet {name} no encontrado, ya fue eliminado")
        else:
            raise

@kopf.timer('toletum.org', 'v1', 'busyboxdaemon', interval=10)
def action_timer(name, namespace, **kwargs):
    v1 = client.CoreV1Api()
    label_selector = f"app={name}"  # Asumí que usás label 'app' con el nombre del DS

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
        cluster_status = json.loads(annotations.get('busyboxdaemons.toletum.org.status'))
    except Exception as ex:
        logger.error("Failed to parse annotation status: %s", ex)
        cluster_status = {}

    logger.info("%s/%s %s", namespace, name, str(cluster_status))


