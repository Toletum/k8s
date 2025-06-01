#!/bin/bash

source colors
source config

NODE="$1"
ACTION="$2"

KUBECTL="$PWD/kubectl --kubeconfig=$PWD/kubeconfig"


if [ "$NODE" == "" ]; then
  msg_error "NODE?"
  exit 1
fi


ip=$(getIP "$NODE")

msg_ok "${NODE}: ${ip}"


if [ "$ACTION" == "INSTALL" ]; then
msg_warm "Installing k8s ${NODE}..."
$SSH root@${ip} '
echo "Installing nfs" > /etc/JCS
apt-get install -y nfs-common open-iscsi vim curl
systemctl enable iscsid
systemctl start iscsid
echo "Installing snap.k8s" > /etc/JCS
snap install k8s --classic
echo "END K8S" > /etc/JCS
reboot
' > /dev/null 2>&1 &


while true; do
  STATUS=$($SSH root@${ip} cat /etc/JCS 2>&1)
  if [ $? -ne 0 ]; then
    STATUS="NO SSH UP&RUNNING"
  fi
  if [ "$STATUS" == "END" ]; then
    STATUS="Waiting..."
  fi
  if [ "$STATUS" == "END K8S" ]; then
    break
  fi
  msg_warm "K8S ${NODE}: ${STATUS}..."
  sleep 5
done
msg_ok "K8S in ${NODE} OK"
fi


if [ "$ACTION" == "MANAGER" ]; then
msg_ok "k8s bootstrap in ${NODE}"
process
$SSH root@${ip} 'k8s bootstrap'
restore
sleep 5

msg_ok "Getting kubeconfig..."
$SSH root@${ip} "k8s kubectl config view --raw" > kubeconfig
sed  -i s/127.0.0.1:6443/${ip}:6443/g kubeconfig
chmod 600 kubeconfig

node_running "${NODE}"
pods_running "${NODE}"
fi


if [ "$ACTION" == "JOIN" ]; then
MANAGER=$($KUBECTL get nodes -o wide| grep "control-plane" | awk '{ print $6}')

msg_ok "Joining $NODE to k8s cluster: $MANAGER"
TOKEN=$($SSH root@${MANAGER} 'k8s get-join-token --worker')
process
$SSH root@${ip}  "k8s join-cluster $TOKEN"
restore
msg_ok "Joined node"

node_running "${NODE}"
pods_running "${NODE}"
fi

