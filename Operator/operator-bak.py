import logging

import kopf
from kubernetes import client, config
from kubernetes.stream import stream
from kubernetes.client.rest import ApiException
import time

import yaml


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("kopf").setLevel(logging.INFO)



try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()
    

def create_admin_user(pod_name, namespace, user, password):
    api = client.CoreV1Api()
    create_user_cmd = f'db.getSiblingDB("admin").createUser({{user:"{user}", pwd:"{password}", roles:[{{role:"root", db:"admin"}}]}})'
    cmd = ["mongosh", "--eval", create_user_cmd]
    try:
        resp = stream(api.connect_get_namespaced_pod_exec,
                      pod_name,
                      namespace,
                      command=cmd,
                      stderr=True, stdin=False,
                      stdout=True, tty=False,
                      _request_timeout=10)
    except Exception:
        resp = "ERROR createUser"
    return resp

def run_rs_initiate(pod_name, namespace, members):
    api = client.CoreV1Api()
    rs_members = [f'{{_id: {i}, host: "{host}"}}' for i, host in enumerate(members)]
    rs_initiate = f'rs.initiate({{_id: "rs0", members: [{", ".join(rs_members)}]}})'

    cmd = ["mongosh", "--eval", rs_initiate]
    
    try:
        resp = stream(api.connect_get_namespaced_pod_exec,
                      pod_name,
                      namespace,
                      command=cmd,
                      stderr=True, stdin=False,
                      stdout=True, tty=False,
                      _request_timeout=10)
    except Exception:
        resp = "ERROR rs.initiate"
    return resp

@kopf.on.create('toletum.org', 'v1', 'mongodaemon')
def create_ds(spec, name, namespace, body, patch, **kwargs):
    members = spec.get("members", [])
    keyfile = spec.get("keyfile", "")
    user = spec.get("user", "")
    password = spec.get("password", "")

    if len(members) < 3:
        raise kopf.PermanentError("Se requieren al menos 3 miembros para el replicaset.")

    api = client.AppsV1Api()
    core_v1 = client.CoreV1Api()
    
    with open("ds_manifest.yaml") as f:
        ds_manifest = yaml.safe_load(f)

    ds_manifest["metadata"]["name"] = name
    cmd_init = f"echo '{keyfile}' > /data/db/keyfile && chmod 400 /data/db/keyfile && chown 999:999 -R /data/db"
    ds_manifest["spec"]["template"]["spec"]["initContainers"][0]["command"][-1] = cmd_init
    
    try:
        api.create_namespaced_daemon_set(namespace=namespace, body=ds_manifest)
    except client.exceptions.ApiException:
        pass

    for i in range(60):
        pods = core_v1.list_namespaced_pod(namespace, label_selector="app=mongo-toletum-org-mongodb").items
        ready_pods = sum(
            1 for pod in pods if pod.status.phase == "Running" and
            any(cond.type == "Ready" and cond.status == "True" for cond in (pod.status.conditions or []))
        )
        logging.info(f"Intento {i+1}: Pods ready {ready_pods}/3")
        if ready_pods >= 3:
            break
        time.sleep(2)
    else:
        raise kopf.TemporaryError("No están los 3 pods listos aún", delay=10)

    pod_name = pods[0].metadata.name
    salida = run_rs_initiate(pod_name, namespace, members)
    logging.info(f"ReplicaSet Setted: {salida.strip()}")
    logging.info(f"CLUSTER DONE ****")

    # Espera menor y con retries
    for _ in range(6):
        pods_primary = core_v1.list_namespaced_pod(namespace, label_selector="mongo-toletum-org-primary=true").items
        if pods_primary:
            break
        logging.info("Esperando pod PRIMARY...")
        time.sleep(5)
    else:
        raise kopf.TemporaryError("No se encontró pod PRIMARY", delay=15)

    salida_user = create_admin_user(pods_primary[0].metadata.name, namespace, user, password)
    logging.info(f"Admin user creation output: {salida_user}")

    kopf.info(body, reason="Created", message=f"DaemonSet {name} creado.")


@kopf.on.delete('toletum.org', 'v1', 'mongodaemon')
def delete_ds(name, namespace, body, patch, **kwargs):
    api = client.AppsV1Api()
    try:
        api.delete_namespaced_daemon_set(name=name, namespace=namespace)
        kopf.info(body, reason="Deleted", message=f"DaemonSet {name} deleted.")
    except client.exceptions.ApiException as ex:
        kopf.event(body, type="Error", reason="DeleteFailed", message=str(ex))
        raise


@kopf.timer('toletum.org', 'v1', 'mongodaemon', interval=5)
def get_primary(spec, status, patch, name, namespace, **kwargs):
    api = client.CoreV1Api()
    primary_label = "mongo-toletum-org-primary"
    disabled_label = "mongo-toletum-org-disabled"

    try:
        pods = api.list_namespaced_pod(namespace, label_selector="app=mongo-toletum-org-mongodb").items
    except Exception as ex:
        logging.error("No hay app=mongo-toletum-org-mongodb")
        return

    for pod in pods:
        pod_name = pod.metadata.name
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
            body = {"metadata": {"labels": {primary_label: label_value}}}
            api.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
        except Exception:
            body = {"metadata": {"labels": {disabled_label: "true"}}}
            api.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)


