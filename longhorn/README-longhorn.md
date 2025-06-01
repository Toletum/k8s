# Longhorn

## YAML
```
wget https://raw.githubusercontent.com/longhorn/longhorn/master/deploy/longhorn.yaml
```


## Edit longhorn.yaml

```
/longhorn-driver-deployer

          - --kubelet-root-dir
          - /var/lib/kubelet
```

## Apply
```

kubectl apply -f longhorn.yaml


kubectl -n longhorn-system get pods


kubectl -n longhorn-system patch svc longhorn-frontend -p '{"spec": {"type": "NodePort"}}'

kubectl get svc -n longhorn-system longhorn-frontend

http://192.168.122.200:31832
```

## Test
```
kubectl apply -f pv-vol.yaml
kubectl apply -f pv.yaml
kubectl apply -f pvc.yaml
kubectl apply -f pv-test.yaml

```

