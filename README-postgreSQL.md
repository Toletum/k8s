helm repo add cnpg https://cloudnative-pg.io/charts
helm repo update

helm install cnpg \
  --namespace default \
  cnpg/cloudnative-pg


kubectl create secret generic carlos-db-secret \
  --from-literal=username=carlos \
  --from-literal=password=carlos \
  --namespace=default

cat <<EOF | kubectl apply -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cluster-carlos
spec:
  instances: 3
  bootstrap:
    initdb:
      owner: carlos
      secret:
        name: carlos-db-secret
  primaryUpdateStrategy: unsupervised
  storage:
    size: 1Gi
EOF


cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: postgres-client
spec:
  containers:
  - name: postgres-client
    image: postgres:latest
    command: ["sleep", "infinity"]
EOF

kubectl exec -ti postgres-client -- psql -h cluster-carlos-rw -U carlos -d postgres





