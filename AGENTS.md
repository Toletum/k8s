# k8s

Notas, manifiestos y scripts para montar un clúster de Kubernetes sobre máquinas virtuales (KVM/libvirt) y desplegar almacenamiento (Longhorn), bases de datos (MongoDB, PostgreSQL, ScyllaDB) y un operador propio de MongoDB.

## Visibilidad y rama
- Público.
- Rama por defecto: no verificado (no se detectó `.git` accesible).

## Stack
- Ubuntu 24.04 (cloud image) en VMs con libvirt/`virt-install`, cloud-init y `qcow2`.
- Kubernetes: instalación con el snap `k8s` (`README-cluster.md`) o con `kubeadm` + flannel (`k8s_node.sh`, `node.sh`).
- Helm (CloudNativePG, `mongo/mongodb_helm/`).
- Longhorn (almacenamiento), metrics-server, Kubernetes Dashboard.
- Operador en Python con kopf 1.38 y `kubernetes` 32.0.1 (`Operator/requirements.txt`).
- Bash.

## Estructura
- `README-cluster.md`: creación de VMs, cloud-init y bootstrap del clúster con el snap `k8s`.
- `k8s_node.sh`: instala y une nodos (`INSTALL`, `MANAGER`, `JOIN`) desde el host usando `virsh` y SSH.
- `node.sh`, `nodes.sh`, `k8s.snap.sh`, `k8s_node.snap.sh`, `k8s.sh` (en `old/`), `delete.sh`: scripts auxiliares de nodos (`old/` es histórico).
- `k8s_node.snap.sh`, `k8s.snap.sh`, `k8s_node.sh`: variantes de la instalación.
- `colors`, `config`: ficheros que sourcean los scripts (colores y variables como `SSH`). `config` puede contener datos sensibles: no leerlo ni copiarlo en respuestas.
- `metrics.yaml`, `admin-user.yaml`, `registry.yaml`: manifiestos de metrics-server, usuario admin del dashboard y registro de contenedores.
- `psql.yaml`: pod cliente de PostgreSQL. `README-postgreSQL.md`: CloudNativePG (3 instancias).
- `longhorn/`: `longhorn.yaml`, PVs y PVC de prueba y `README-longhorn.md`.
- `mongo/`: StatefulSet, DaemonSet, cluster con KubeDB y un chart Helm (`mongodb_helm/`) para MongoDB (replica set `rs0`).
- `scylladb/`: `scylladb.yaml`, `scylladb.sh` y `p.py`.
- `Operator/`: operador kopf (`operator.py`, `helpers.py`, `consts.py`) que gestiona el CRD `MongoDaemon` (`toletum.org/v1`) y crea un DaemonSet de MongoDB. `BusyBox/` es un operador de prueba. `operator-bak.py` y `operator-bb.py` son copias antiguas o de prueba.

## Comandos
Los comandos vienen de los README y scripts; no se han ejecutado:
- Crear VMs: `virt-install ...` (ver `README-cluster.md`).
- Bootstrap: `k8s bootstrap` en el manager y `k8s join-cluster <token>` en los workers (`README-cluster.md`).
- Gestión de nodos desde el host: `./k8s_node.sh <nodo> INSTALL|MANAGER|JOIN`.
- Operador: `kubectl apply -f mongodaemon-crd.yaml`; `kopf run operator.py --namespace=default` (con `KUBECONFIG` apuntando al clúster).
- Operador en contenedor: el Dockerfile del README usa `python:3.11-slim` y `kopf run --standalone`.
- Mongo: `kubectl apply -f mongo-statefulset.yaml` (o `mongo.yaml` del operador).
- Postgres: `helm install cnpg cnpg/cloudnative-pg` y luego el Cluster de `README-postgreSQL.md`.
- Longhorn: `kubectl apply -f longhorn.yaml`.

## Configuración
- `Operator/consts.py`: etiquetas y nombres (`toletum.org`, `v1`, `mongodaemon`, `mongo-toletum-org-mongodb` como etiqueta de nodo). El operador necesita al menos 3 nodos con esa etiqueta.
- Variables/ficheros: `config` (variables de `k8s_node.sh`; valores no incluidos aquí), `keys` (claves SSH generadas con `ssh-keygen`; no versionar), `kubeconfig` (no versionar).
- Secretos creados con `kubectl create secret` (`mongo-keyfile`, `carlos-db-secret`): las instrucciones los generan; no escribirlos en ficheros del repo.
- IPs fijas en las notas: 192.168.122.200–203 (red `virbr0`).

## Convenciones para agentes
- No escribir contraseñas, claves SSH, `kubeconfig` ni tokens en el repo ni en respuestas. Los README contienen contraseñas de ejemplo (`admin`, usuario de Postgres): son solo de laboratorio, no reutilizarlas.
- Los `*.yaml` son manifiestos aplicados a mano: revisar el namespace antes de `kubectl apply` o `delete`.
- Los scripts ejecutan `ssh` y `apt` en nodos remotos y `virsh`: no ejecutarlos sin confirmación (`delete.sh`, `node.sh`).
- Las rutas en los README apuntan a `/home/toletum/...`: son rutas del entorno original.

## Estado
- No hay tests ni CI.
- `k8s_node.sh` añade la clave del repositorio de Kubernetes v1.29 pero el repositorio de paquetes apunta a v1.33: versiones inconsistentes.
- Los README mezclan Dockerfile y `requirements.txt` dentro de `Operator/README.md` (no son ficheros separados).
- `Operator/operator.py` tiene código y comentarios en español con restos del operador BusyBox (`create_ds` mencionan `BusyboxDaemon`): revisar.
- `Operator/operator-bak.py` y `Operator/BusyBox/` parecen copias antiguas o de prueba.
- `mongo/mongodb_helm/mi-chart/1` es un fichero sin extensión sin uso aparente.
- Hay muchos scripts y manifiestos sueltos con nombres similares (`k8s.sh`, `k8s.snap.sh`, `k8s_node.sh`, `k8s_node.snap.sh`, `node.sh`, `nodes.sh`): no está documentado cuál es el flujo actual.
- No verificado: qué manifiestos están desplegados ahora mismo.
