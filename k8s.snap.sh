#!/bin/bash

source colors
source config

readarray -t NODES < <(virsh list --name)
MANAGER=${NODES[0]}
WORKERS=${NODES[@]:1}


if [ ! -f ./kubectl ]; then
curl -LO "https://dl.k8s.io/release/v1.32.3/bin/linux/amd64/kubectl"
chmod +x ./kubectl
fi

if [ ! -f ./helm ]; then
curl -LO https://get.helm.sh/helm-v3.14.3-linux-amd64.tar.gz
tar --extract --file=helm-v3.14.3-linux-amd64.tar.gz linux-amd64/helm
mv linux-amd64/helm .
fi

msg_ok "MANAGER: ${MANAGER} WORKERS: ${WORKERS}"

for NODE in ${NODES[@]}; do
{
  ./k8s_node.snap.sh ${NODE} INSTALL
}&
done && wait

./k8s_node.snap.sh ${MANAGER} MANAGER


msg_ok "Joining nodes to k8s cluster"
for NODE in ${WORKERS}; do
{
  ./k8s_node.snap.sh ${NODE} JOIN
}&
done && wait
msg_ok "Joined nodes"

# Dashboard
if [ "$DASHBOARD" == "true" ]; then
KUBECTL="$PWD/kubectl --kubeconfig=$PWD/kubeconfig"
$KUBECTL apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
$KUBECTL apply -f admin-user.yaml
$KUBECTL -n kubernetes-dashboard patch svc kubernetes-dashboard -p '{"spec": {"type": "NodePort"}}'
process
$KUBECTL -n kubernetes-dashboard create token admin-user
restore

PORT=$($KUBECTL -n kubernetes-dashboard get svc kubernetes-dashboard -o=jsonpath="{.spec.ports[0].nodePort}")


ip=$(getIP ${MANAGER})
msg_ok "https://${ip}:${PORT}"
fi

cat <<EOF
alias kubectl="$PWD/kubectl --kubeconfig=$PWD/kubeconfig"
alias helm="$PWD/helm --kubeconfig=$PWD/kubeconfig"
export KUBECONFIG="$PWD/kubeconfig"
EOF


exit 0


