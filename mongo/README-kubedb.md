
helm repo add appscode https://charts.appscode.com/stable/
helm repo update
helm search repo appscode/kubedb --version=v2025.4.30
#helm upgrade -i kubedb appscode/kubedb -n kubedb --create-namespace --version=v2025.4.30


helm install kubedb appscode/kubedb \
  --namespace kubedb --create-namespace \
  --set kubedb.enabled=true \
  --set mongodb.enabled=true \
  --set-file global.license=/path/to/license.txt


kubectl --namespace kubedb get pods

kubectl --namespace kubedb get pods
kubectl get crds | grep kubedb.com


apiVersion: kubedb.com/v1alpha2
kind: MongoDB
metadata:
  name: my-mongo
  namespace: default
spec:
  version: "5.0.15"
  replicas: 3
  replicaSet:
    name: rs0
  storage:
    accessModes:
      - ReadWriteOnce
    resources:
      requests:
        storage: 10Gi


kubectl port-forward svc/my-mongo 27017
 
