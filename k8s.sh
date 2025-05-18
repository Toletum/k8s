#!/bin/bash

source config


for key in "${!NODES[@]}"; do
    echo -e "${GREEN} K8S Installing... ${key} (${NODES[$key]})...${RESET}"
{
ssh -t -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} '
apt-get install -y nfs-common open-iscsi vim curl qemu-guest-agent
systemctl enable iscsid
systemctl start iscsid
snap install k8s --classic
sudo systemctl start qemu-guest-agent
sudo systemctl enable qemu-guest-agent
reboot
' > /dev/null 2>&1
} &

done

echo -e "${GREEN} Waiting k8s & reboot...${RESET}"
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
chmod 600 kubeconfig

if [ ! -f ./kubectl ]; then
curl -LO "https://dl.k8s.io/release/v1.32.3/bin/linux/amd64/kubectl"
chmod +x ./kubectl
fi

if [ ! -f ./helm ]; then
curl -LO https://get.helm.sh/helm-v3.14.3-linux-amd64.tar.gz
tar --extract --file=helm-v3.14.3-linux-amd64.tar.gz linux-amd64/helm
mv linux-amd64/helm .
fi


export KUBECONFIG="$PWD/kubeconfig"
KUBECTL="$PWD/kubectl --kubeconfig=$PWD/kubeconfig"

$KUBECTL taint nodes node01 node-role.kubernetes.io/master=:NoSchedule


echo -e "${GREEN} Joining nodos to k8s cluster ${RESET}"
sleep 10
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
s=$($KUBECTL get nodes --no-headers | awk '{print "-",$2,"-"}')
sleep 1
pending=$(echo "$s" | grep -v " Ready " | wc -l)
echo -e "${YELLOW} Nodes no ready: $pending... ${RESET}"
done
echo -e "${GREEN} All nodes Ready RUNNING ${RESET}"


pending=1
while [ $pending -gt 0 ]; do
echo -e "${YELLOW} Waiting all pods RUNNING... ${RESET}"
s=$($KUBECTL get pods -A --no-headers | awk '{print $4}')
sleep 1
pending=$(echo "$s" | grep -v "Running" | wc -l)
echo -e "${YELLOW} Pods no running $pending... ${RESET}"
done
echo -e "${GREEN} All pods RUNNING ${RESET}"


# Dashboard
if [ "$DASHBOARD" == "true" ]; then

$KUBECTL apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
$KUBECTL apply -f admin-user.yaml
$KUBECTL -n kubernetes-dashboard patch svc kubernetes-dashboard -p '{"spec": {"type": "NodePort"}}'
$KUBECTL -n kubernetes-dashboard create token admin-user

PORT=$($KUBECTL -n kubernetes-dashboard get svc kubernetes-dashboard -o=jsonpath="{.spec.ports[0].nodePort}")

echo "https://${MANAGER}:${PORT}"
fi

cat <<EOF
alias kubectl="$PWD/kubectl --kubeconfig=$PWD/kubeconfig"
alias helm="$PWD/helm --kubeconfig=$PWD/kubeconfig"
export KUBECONFIG="$PWD/kubeconfig"
EOF


exit 0

apiVersion: apps/v1
kind: Deployment
metadata:
  name: registry
  labels:
    app: registry
spec:
  replicas: 1
  selector:
    matchLabels:
      app: registry
  template:
    metadata:
      labels:
        app: registry
    spec:
      containers:
      - name: registry
        image: registry:2
        ports:
        - containerPort: 5000
        volumeMounts:
        - name: registry-storage
          mountPath: /var/lib/registry
      volumes:
      - name: registry-storage
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: registry
spec:
  selector:
    app: registry
  ports:
  - protocol: TCP
    port: 5000
    targetPort: 5000
  type: NodePort



