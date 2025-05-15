
ssh -i keys root@192.168.122.200

python -m venv .venv
source .venv/bin/activate

pip install kopf kubernetes


kubectl apply -f busyboxdaemon-crd.yaml


export KUBECONFIG=/home/toletum/k8s/kubeconfig
kopf run operator.py --namespace=default

kubectl apply -f mongo.yaml


POD=$(kubectl get pods -l mongo.toletum.org/primary=true -o jsonpath='{.items[*].metadata.name}')

kubectl exec $POD -- mongosh mongodb://127.0.0.1:27017/admin -eval '
db.createUser({
  user: "admin",
  pwd: "admin",  // Cambia esto por una contraseña segura
  roles: [{ role: "root", db: "admin" }]
});
'


kubectl exec $POD -- mongosh 'mongodb://admin:admin@127.0.0.1:27017/?directConnection=false&appName=mongosh+2.5.0&readPreference=primary'



kubectl delete -f mongo.yaml

for key in "${!NODES[@]}"; do
ssh -o StrictHostKeyChecking=no -i ../keys root@${NODES[$key]} rm -rvf /data/db
done

