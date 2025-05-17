
ssh -i keys root@192.168.122.200

python -m venv .venv
source .venv/bin/activate

pip install kopf kubernetes


kubectl apply -f mongodaemon-crd.yaml


kubectl label nodes node02 mongo-toletum-org-mongodb=true
kubectl label nodes node03 mongo-toletum-org-mongodb=true
kubectl label nodes node04 mongo-toletum-org-mongodb=true

export KUBECONFIG=/home/toletum/k8s/kubeconfig
kopf run operator.py --namespace=default


for key in "${!NODES[@]}"; do
{
echo "$key"
ssh -o StrictHostKeyChecking=no -i ../keys root@${NODES[$key]} mkdir -p /data/db
} &
done && wait


kubectl apply -f mongo.yaml


POD=$(kubectl get pods -l mongo-toletum-org-primary=true -o  jsonpath='{.items[0].metadata.name}')
kubectl exec -ti $POD -- mongosh 'mongodb://admin:admin@127.0.0.1:27017/?directConnection=false&appName=mongosh+2.5.0&readPreference=primary'



kubectl delete -f mongo.yaml

for key in "${!NODES[@]}"; do
{
echo "$key"
ssh -o StrictHostKeyChecking=no -i ../keys root@${NODES[$key]} rm -rf /data
} &
done && wait


for key in "${!NODES[@]}"; do
echo "$key"
ssh -o StrictHostKeyChecking=no -i ../keys root@${NODES[$key]} ls -la /data
done

kubectl patch MongoDaemon mongo-cluster-1 -p '{"status": null}' --type=merge


