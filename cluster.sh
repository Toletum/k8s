#!/bin/bash

echo "Nodes Installing...."
for node in $NODES
do
ssh -t -o StrictHostKeyChecking=no -i keys root@${node} '
apt update && sudo apt upgrade -y
apt-get install -y nfs-common qemu-guest-agent open-iscsi vim
systemctl enable qemu-guest-agent
systemctl start qemu-guest-agent
systemctl enable iscsid
systemctl start iscsid
snap install k8s --classic
reboot
'
done


echo "Nodes Uping...."
for node in $NODES
do
  s=1
  while [ $s -ne 0 ]
  do
    echo "  ${node}..."
    ssh -o StrictHostKeyChecking=no -i keys root@${node} ls >/dev/null 2>&1
    s=$(echo $?)
  done
  echo "  ${node} OK"
done



ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} 'k8s bootstrap'


for w in ${WORKERS}
do
TOKEN=$(ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} 'k8s get-join-token --worker')
ssh -o StrictHostKeyChecking=no -i keys root@${w}  "k8s join-cluster $TOKEN"
done



echo "nodes Ready..."
for label in $LABELS
do
s="XXX"
while [ "$s" != "True" ];
do
echo "  ${label}..."
s=$(ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} "k8s kubectl get node ${label} -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'")
done
echo "  ${label} Ready"
done


# Dashboard
scp -o StrictHostKeyChecking=no -i keys admin-user.yaml root@${MANAGER}:

ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} "
k8s kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
k8s kubectl apply -f admin-user.yaml
k8s kubectl -n kubernetes-dashboard patch svc kubernetes-dashboard -p '{\"spec\": {\"type\": \"NodePort\"}}'
k8s kubectl -n kubernetes-dashboard create token admin-user
echo
"

PORT=$(ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} '
k8s kubectl -n kubernetes-dashboard get svc kubernetes-dashboard -o=jsonpath="{.spec.ports[0].nodePort}"
')


echo "https://${MANAGER}:${PORT}"


