from kubernetes import client, config
from kubernetes.stream import stream

import secrets
import base64

from consts import LABELS, logger

def run_rs_initiate(pod_name, namespace, pod_items):
    core = client.CoreV1Api()
    cluster_nodes = []
    for pod in pod_items:
        node_name = pod.spec.node_name
        node = core.read_node(node_name)
        node_ip = next(addr.address for addr in node.status.addresses if addr.type == "InternalIP")
        cluster_nodes.append({
            'name': node_name,
            'ip': node_ip
        })


    rs_members = [
        f'{{_id: {i}, host: "{node["ip"]}:27017"}}'
        for i, node in enumerate(cluster_nodes)
    ]

    logger.info("replicaSet members %s", str(rs_members))

    rs_initiate = f'rs.initiate({{_id: "rs0", members: [{", ".join(rs_members)}]}})'
    cmd = ["mongosh", "--eval", rs_initiate]

    try:
        resp = stream(
            core.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=cmd,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _request_timeout=10,
        )
        return resp.strip()
    except Exception as e:
        return f"Error running rs.initiate: {e}"


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
        body = {"metadata": {"labels": {LABELS['primary_label']: label_value, LABELS['disabled_label']: None}}}
        api.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
        return True if resp == "true" else False
    except Exception as ex:
        body = {"metadata": {"labels": {
            LABELS['disabled_label']: "true",
            LABELS['primary_label']: None
        }}}
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

def generate_keyfile():
    raw = secrets.token_bytes(756)
    return base64.b64encode(raw).decode()

