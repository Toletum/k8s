
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




FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["kopf", "run", "--standalone", "your_operator_file.py"]

kopf
kubernetes
pyyaml


aiohappyeyeballs==2.6.1
aiohttp==3.11.18
aiosignal==1.3.2
attrs==25.3.0
cachetools==5.5.2
certifi==2025.4.26
charset-normalizer==3.4.2
click==8.2.0
durationpy==0.9
frozenlist==1.6.0
google-auth==2.40.1
idna==3.10
iso8601==2.1.0
kopf==1.38.0
kubernetes==32.0.1
multidict==6.4.3
oauthlib==3.2.2
propcache==0.3.1
pyasn1==0.6.1
pyasn1_modules==0.4.2
python-dateutil==2.9.0.post0
python-json-logger==3.3.0
PyYAML==6.0.2
requests==2.32.3
requests-oauthlib==2.0.0
rsa==4.9.1
six==1.17.0
urllib3==2.4.0
websocket-client==1.8.0
yarl==1.20.0
