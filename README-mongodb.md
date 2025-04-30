# MongoDB ReplicaSet

## Network
```
kubectl apply -f mongo-net.yaml
```


## Mongodb
```
kubectl apply -f mongo-statefulset.yaml
```


## Active RS
```
kubectl apply -f mongo-job.yaml
```

## Status
```
kubectl exec -ti mongo-0 -- mongosh -eval 'rs.status()'
```

## Test
```
kubectl exec -ti mongo-0 -- mongosh "mongodb://192.168.122.200:30000,192.168.122.201:30001,192.168.122.202:30002/?replicaSet=rs0"
```


