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

msg_ok "Getting IP for ${NODE}"
ip=$(virsh domifaddr "$NODE" | awk '/vnet/ {print $4}' | cut -d'/' -f1)

msg_ok "${NODE} ${ip}"


$SSH root@${ip} hostname > /dev/null 2>&1

if [ $? -ne 0 ]; then
msg_error "${NODE} ${ip}: NO SSH"
exit 1
fi

msg_ok "${NODE} ${ip}: SSH OK -> ${ACTION}"


if [ "$ACTION" == "INSTALL" ];then
msg_ok "K8S Installing... ${NODE}"
$SSH root@${ip} '

echo "K8S Installing: netfilter..." > /etc/JCS

cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
br_netfilter
EOF

sudo modprobe br_netfilter

sudo sysctl net.bridge.bridge-nf-call-iptables=1
sudo sysctl net.bridge.bridge-nf-call-ip6tables=1


echo "K8S Installing: bridge..." > /etc/JCS
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sudo sysctl --system


echo "K8S Installing: nfs..." > /etc/JCS
apt-get install -y nfs-common open-iscsi vim curl
systemctl enable iscsid
systemctl start iscsid

echo "K8S Installing: containerd..." > /etc/JCS
apt update && apt install -y containerd
mkdir -p /etc/containerd
containerd config default | tee /etc/containerd/config.toml
systemctl restart containerd && systemctl enable containerd

echo "K8S Installing: certificates..." > /etc/JCS
sudo apt update && sudo apt install -y apt-transport-https ca-certificates curl

echo "K8S Installing: keyrings..." > /etc/JCS
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | \
sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo "K8S Installing: kubernetes.list..." > /etc/JCS
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.33/deb/ /" | \
  sudo tee /etc/apt/sources.list.d/kubernetes.list

echo "K8S Installing: Update..." > /etc/JCS
sudo apt update
echo "K8S Installing: k8s packages..." > /etc/JCS
sudo apt install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
echo "END K8S" > /etc/JCS

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


if [ "$ACTION" == "MANAGER" ];then
msg_ok "Control-plain... ${ip}"
$SSH root@${ip} '
sudo kubeadm init --pod-network-cidr=10.244.0.0/16

mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config


kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
'
scp -o StrictHostKeyChecking=no -i data/keys root@${ip}:/root/.kube/config kubeconfig

node_running "${NODE}"
pods_running "${NODE}"

cat <<EOF
export KUBECONFIG="$PWD/kubeconfig"
alias kubectl="$PWD/kubectl --kubeconfig=$PWD/kubeconfig"
EOF

# https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# --kubelet-insecure-tls=true
$KUBECTL apply -f metrics.yaml

fi

if [ "$ACTION" == "JOIN" ];then

MANAGER=$($KUBECTL get nodes -o wide| grep "control-plane" | awk '{ print $6}')

msg_ok "Worker... ${ip} joinng to ${MANAGER}"

TOKEN=$($SSH root@${MANAGER} '
kubeadm token create --print-join-command
' | tr -d '\r')


$SSH root@${ip} "${TOKEN}"

node_running "${NODE}"
pods_running "${NODE}"


$KUBECTL label node ${NODE} node-role.kubernetes.io/worker=

fi

