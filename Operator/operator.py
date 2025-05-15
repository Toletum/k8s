import kopf
from kubernetes import client, config
from kubernetes.stream import stream
import time


try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()


started = False


def run_rs_initiate(pod_name, namespace):
    api = client.CoreV1Api()
    cmd = [
        "mongosh", "--eval",
        'rs.initiate({_id: "rs0", members: [ {_id: 1, host: "192.168.122.201:27017"}, {_id: 2, host: "192.168.122.202:27017"}, {_id: 3, host: "192.168.122.203:27017"} ]})'
    ]
    resp = stream(api.connect_get_namespaced_pod_exec,
                  pod_name,
                  namespace,
                  command=cmd,
                  stderr=True, stdin=False,
                  stdout=True, tty=False)
    return resp


@kopf.on.create('toletum.org', 'v1', 'mongodaemon')
def create_ds(spec, name, namespace, body, **kwargs):
    global started
    
    api = client.AppsV1Api()
    core_v1 = client.CoreV1Api()
    
    ds_manifest = {
        "apiVersion": "apps/v1",
        "kind": "DaemonSet",
        "metadata": {
            "name": name,
            "labels": {"app": "mongo"}
        },
        "spec": {
            "selector": {
                "matchLabels": {"app": "mongo"}
            },
            "template": {
                "metadata": {
                    "labels": {"app": "mongo"}
                },
                "spec": {
                    "hostNetwork": True,
                    "dnsPolicy": "ClusterFirstWithHostNet",
                    "affinity": {
                        "nodeAffinity": {
                            "requiredDuringSchedulingIgnoredDuringExecution": {
                                "nodeSelectorTerms": [{
                                    "matchExpressions": [{
                                        "key": "node-role.kubernetes.io/control-plane",
                                        "operator": "DoesNotExist"
                                    }]
                                }]
                            }
                        },
                        "podAntiAffinity": {
                            "requiredDuringSchedulingIgnoredDuringExecution": [{
                                "labelSelector": {
                                    "matchLabels": {"app": "mongo"}
                                },
                                "topologyKey": "kubernetes.io/hostname"
                            }]
                        }
                    },
                    "initContainers": [{
                        "name": "init-keyfile",
                        "image": "busybox",
                        "command": [
                            "sh", "-c",
                            "echo 'kzIZMBM2EUEXAT5wZpp8st555gxWv54xabVJrLR4xGPUUrFn7uqLTdfsRIjPYu/k' > /data/db/keyfile && chmod 400 /data/db/keyfile && chown 999:999 -R /data/db"
                        ],
                        "volumeMounts": [{
                            "name": "mongo-data",
                            "mountPath": "/data/db"
                        }]
                    }],
                    "containers": [{
                        "name": "mongo",
                        "image": "mongo:8.0",
                        "args": [
                            "--replSet", "rs0",
                            "--bind_ip_all",
                            "--auth",
                            "--keyFile=/data/db/keyfile"
                        ],
                        "ports": [{"containerPort": 27017}],
                        "volumeMounts": [{
                            "name": "mongo-data",
                            "mountPath": "/data/db"
                        }],
                        "readinessProbe": {
                            "exec": {
                                "command": ["mongosh", "--eval", "db.adminCommand('ping')"]
                            },
                            "initialDelaySeconds": 10,
                            "periodSeconds": 5,
                            "timeoutSeconds": 3,
                            "failureThreshold": 5
                        },
                        "livenessProbe": {
                            "exec": {
                                "command": ["mongosh", "--eval", "db.adminCommand('ping')"]
                            },
                            "initialDelaySeconds": 30,
                            "periodSeconds": 10,
                            "timeoutSeconds": 5,
                            "failureThreshold": 3
                        }
                    }],
                    "volumes": [{
                        "name": "mongo-data",
                        "hostPath": {
                            "path": "/data/db",
                            "type": "DirectoryOrCreate"
                        }
                    }]
                }
            }
        }
    }

    api.create_namespaced_daemon_set(namespace=namespace, body=ds_manifest)
    
    for _ in range(60):  # hasta 2 minutos aprox (60*2 seg)
        pods = core_v1.list_namespaced_pod(namespace, label_selector="app=mongo")
        ready_pods = 0
        for pod in pods.items:
            if pod.status.phase == "Running":
                conditions = pod.status.conditions or []
                for cond in conditions:
                    if cond.type == "Ready" and cond.status == "True":
                        ready_pods += 1
                        break
        if ready_pods >= 3:
            break
        time.sleep(2)
    else:
        raise kopf.TemporaryError("No están los 3 pods listos aún", delay=10)

    # Ejecutar rs.initiate en uno de los pods
    pod_name = pods.items[0].metadata.name
    salida = run_rs_initiate(pod_name, namespace)
    print(f"ReplicaSet Setted: {salida}")
    started = True

    kopf.info(body, reason="Created", message=f"DaemonSet {name} creado.")


@kopf.on.delete('toletum.org', 'v1', 'mongodaemon')
def delete_ds(name, namespace, body, **kwargs):
    global started
    api = client.AppsV1Api()
    try:
        started = False
        api.delete_namespaced_daemon_set(name=name, namespace=namespace)
        kopf.info(body, reason="Deleted", message=f"DaemonSet {name} deleted.")
    except client.exceptions.ApiException as e:
        kopf.event(body, type="Error", reason="DeleteFailed", message=str(e))
        raise


@kopf.timer('toletum.org', 'v1', 'mongodaemon', interval=10)
def getPrimary(spec, name, namespace, **kwargs):
    if not started:
        return    
    
    api = client.CoreV1Api()
    core_v1 = client.CoreV1Api()
    
    pods = core_v1.list_namespaced_pod(namespace, label_selector="app=mongo")
    for pod in pods.items:
      pod_name = pod.metadata.name
      cmd = [
        "mongosh", "--eval",
        'rs.isMaster().ismaster'
      ] 
      resp = stream(api.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace,
                    command=cmd,
                    stderr=True, stdin=False,
                    stdout=True, tty=False)
      body = {
        "metadata": {
            "labels": {
                "mongo.toletum.org/primary": resp.strip().lower()
            }
        }
      }
      api.patch_namespaced_pod(name=pod_name, namespace=namespace, body=body)
    
      if resp.strip().lower() == "true":
          print(f"********* PRIMARY POD: {pod.metadata.name}")
      

