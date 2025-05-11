# MongoDB ReplicaSet


openssl rand -base64 756 > keyfile
chmod 600 keyfile

kubectl create secret generic mongo-keyfile --from-file=./keyfile


## Mongodb
```
kubectl apply -f mongo-statefulset.yaml

kubectl get pods -w
```


## Active RS
```
kubectl apply -f mongo-job.yaml
```

## Status
```
kubectl exec -ti mongo-0 -- mongosh -eval 'rs.status()'
```

```
kubectl exec -it mongo-0 -- mongosh -eval '
use admin

db.createUser({
  user: "admin",
  pwd: "admin",  // Cambia esto por una contraseña segura
  roles: [{ role: "root", db: "admin" }]
});
'

```


## Test
```
kubectl exec -ti mongo-0 -- mongosh "mongodb://192.168.122.200:27017,192.168.122.201:27017,192.168.122.202:27017/?replicaSet=rs0"
```


