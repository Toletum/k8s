#!/bin/bash

source config


for key in "${!NODES[@]}"; do
  {
    echo -e "${GREEN} K8S Installing... ${key} (${NODES[$key]})...${RESET}"

ssh -t -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} '
apt update && sudo apt upgrade -y
apt-get install -y nfs-common qemu-guest-agent open-iscsi vim
systemctl enable qemu-guest-agent
systemctl start qemu-guest-agent
systemctl enable iscsid
systemctl start iscsid
snap install k8s --classic
reboot
' > /dev/null 2>&1

    echo -e "${GREEN} Node ${key} Reboot.${RESET}"

  } &
done

wait

for key in "${!NODES[@]}"; do
  s=1
  while [ $s -ne 0 ]
  do
    echo -e "${YELLOW} Waiting ${key}...${RESET}"
    ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} ls >/dev/null 2>&1
    s=$(echo $?)
    sleep 1
  done
    echo -e "${GREEN} ${key} OK ${RESET}"
done


echo -e "${GREEN} k8s bootstrap in ${MANAGER}${RESET}"
ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} 'k8s bootstrap'


ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER}  "k8s kubectl config view --raw" > kubeconfig
sed  -i s/127.0.0.1:6443/${MANAGER}:6443/g kubeconfig
if [ ! -f ./kubectl ]; then
curl -LO "https://dl.k8s.io/release/v1.32.3/bin/linux/amd64/kubectl"
chmod +x ./kubectl
fi

alias kubectl="./kubectl --kubeconfig=kubeconfig"


echo -e "${GREEN} Joining nodos to k8s cluster ${RESET}"
for key in "${!NODES[@]}"; do
  if [ "${MANAGER}" == "${NODES[$key]}" ]; then
    echo -e "${YELLOW} ${key} is manager ${RESET}"
    continue
  fi
  {
  echo -e "${GREEN} ${key} joing... ${RESET}"
  TOKEN=$(ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} 'k8s get-join-token --worker')
  ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]}  "k8s join-cluster $TOKEN"
  } &
done

wait


pending=1
while [ $pending -gt 0 ]; do
echo -e "${YELLOW} Waiting all nodes Ready... ${RESET}"
s=$(kubectl get nodes --no-headers | awk '{print "-",$2,"-"}')
sleep 1
pending=$(echo "$s" | grep -v " Ready " | wc -l)
echo -e "${YELLOW} Nodes no ready: $pending... ${RESET}"
done
echo -e "${GREEN} All nodes Ready RUNNING ${RESET}"


pending=1
while [ $pending -gt 0 ]; do
echo -e "${YELLOW} Waiting all pods RUNNING... ${RESET}"
s=$(kubectl get pods -A --no-headers | awk '{print $4}')
pending=$(echo "$s" | grep -v "Running" | wc -l)
echo -e "${YELLOW} Pods no running $pending... ${RESET}"
done
echo -e "${GREEN} All pods RUNNING ${RESET}"


# Dashboard
if [ "$DASHBOARD" == "true" ]; then

kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
kubectl apply -f admin-user.yaml
kubectl -n kubernetes-dashboard patch svc kubernetes-dashboard -p '{"spec": {"type": "NodePort"}}'
kubectl -n kubernetes-dashboard create token admin-user

PORT=$(kubectl -n kubernetes-dashboard get svc kubernetes-dashboard -o=jsonpath="{.spec.ports[0].nodePort}")

echo "https://${MANAGER}:${PORT}"
fi


