#!/bin/bash

source config


echo "K8S Installing...."
for key in "${!NODES[@]}"; do
  {
    echo -e "${GREEN} Node ${key} (${NODES[$key]})...${RESET}"

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


echo "Nodes ready...."
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


ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} 'k8s bootstrap'


for key in "${!NODES[@]}"; do
  if [ "${MANAGER}" == "${NODES[$key]}" ]; then
    echo "${key} is the manager"
    continue
  fi
  TOKEN=$(ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} 'k8s get-join-token --worker')
  ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]}  "k8s join-cluster $TOKEN"
done



for key in "${!NODES[@]}"; do
  s="XXX"
  while [ "$s" != "True" ];
  do
    echo -e "${YELLOW} Waiting ${key}...${RESET}"
    s=$(ssh -o StrictHostKeyChecking=no -i keys root@${MANAGER} "k8s kubectl get node ${key} -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'")
    sleep 1
  done
  echo -e "${GREEN} ${key} READY ${RESET}"
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


