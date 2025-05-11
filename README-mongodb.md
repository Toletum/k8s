# MongoDB ReplicaSet


openssl rand -base64 756 > keyfile

kubectl create secret generic mongo-keyfile --from-file=./keyfile


## Mongodb
```
kubectl apply -f mongo-statefulset.yaml

kubectl get pods -l app=mongo
```


## Active RS
```
kubectl exec -ti mongo-0 -c mongo -- mongosh -eval '
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "192.168.122.200:27017" },
    { _id: 1, host: "192.168.122.201:27017" },
    { _id: 2, host: "192.168.122.202:27017" }
  ]
});
'

```

## Status
```
kubectl exec -ti mongo-0 -c mongo -- mongosh -eval 'rs.status()'
```

## Admin User
```
kubectl exec -it mongo-0 -c mongo -- mongosh mongodb://127.0.0.1:27017/admin -eval '
db.createUser({
  user: "admin",
  pwd: "admin",  // Cambia esto por una contraseña segura
  roles: [{ role: "root", db: "admin" }]
});


db.getUsers()
'

```


## Test
```
kubectl exec -ti mongo-0 -- mongosh "mongodb://admin:admin@192.168.122.200:27017,192.168.122.201:27017,192.168.122.202:27017/?replicaSet=rs0"
```


