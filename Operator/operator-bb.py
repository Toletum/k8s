import kopf
from kubernetes import client, config

# Cargar configuración K8s
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

@kopf.on.create('toletum.org', 'v1', 'busyboxdaemon')
def create_ds(spec, name, namespace, **kwargs):
    api = client.AppsV1Api()

    ds_manifest = {
        "apiVersion": "apps/v1",
        "kind": "DaemonSet",
        "metadata": {
            "name": name,
            "labels": {"app": name}
        },
        "spec": {
            "selector": {
                "matchLabels": {"app": name}
            },
            "template": {
                "metadata": {
                    "labels": {"app": name}
                },
                "spec": {
                    "containers": [{
                        "name": "busybox",
                        "image": "busybox",
                        "command": ["sleep", "infinity"]
                    }]
                }
            }
        }
    }

    api.create_namespaced_daemon_set(namespace=namespace, body=ds_manifest)
    print(f"DaemonSet {name} creado en {namespace}")

@kopf.on.delete('toletum.org', 'v1', 'busyboxdaemon')
def delete_ds(name, namespace, **kwargs):
    api = client.AppsV1Api()
    api.delete_namespaced_daemon_set(name=name, namespace=namespace)
    print(f"DaemonSet {name} eliminado de {namespace}")

