# Cluster k8s

## Create cluster

### Download ubuntu server image
```
wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img -O ubuntu24.img

qemu-img convert -f qcow2 -O qcow2 ubuntu24.img manager.qcow2
qemu-img resize manager.qcow2 +20G

qemu-img convert -f qcow2 -O qcow2 ubuntu24.img w01.qcow2
qemu-img resize w01.qcow2 +20G

qemu-img convert -f qcow2 -O qcow2 ubuntu24.img w02.qcow2
qemu-img resize w02.qcow2 +20G
```


### create ssh keys
```
ssh-keygen -f keys
```

### create cloud-init.iso
Edit keys.pub

```
cloud-localds cloud-init-manager.iso user-data-manager meta-data-manager
cloud-localds cloud-init-w01.iso user-data-w01 meta-data-w01
cloud-localds cloud-init-w02.iso user-data-w02 meta-data-w02
```


### create Manager
```
virt-install \
  --name manager \
  --ram=4096 \
  --vcpus=2 \
  --disk path=manager.qcow2,format=qcow2 \
  --disk path=cloud-init-manager.iso,device=cdrom \
  --os-variant ubuntu24.04 \
  --network bridge=virbr0,model=virtio \
  --import \
  --graphics none &
```

### create workers
```
virt-install \
  --name w01 \
  --ram=4096 \
  --vcpus=2 \
  --disk path=w01.qcow2,format=qcow2 \
  --disk path=cloud-init-w01.iso,device=cdrom \
  --os-variant ubuntu24.04 \
  --network bridge=virbr0,model=virtio \
  --import \
  --graphics none &


virt-install \
  --name w02 \
  --ram=4096 \
  --vcpus=2 \
  --disk path=w02.qcow2,format=qcow2 \
  --disk path=cloud-init-w02.iso,device=cdrom \
  --os-variant ubuntu24.04 \
  --network bridge=virbr0,model=virtio \
  --import \
  --graphics none &
```


### Check k8s snap
```
ssh-keygen -f '/home/toletum/.ssh/known_hosts' -R '192.168.122.200'
ssh-keygen -f '/home/toletum/.ssh/known_hosts' -R '192.168.122.201'
ssh-keygen -f '/home/toletum/.ssh/known_hosts' -R '192.168.122.202'


ssh -o StrictHostKeyChecking=no -i keys root@192.168.122.200 'snap list k8s 2>/dev/null || echo "WAITING"'
ssh -o StrictHostKeyChecking=no -i keys root@192.168.122.201 'snap list k8s 2>/dev/null || echo "WAITING"'
ssh -o StrictHostKeyChecking=no -i keys root@192.168.122.202 'snap list k8s 2>/dev/null || echo "WAITING"'
```
                    

## k8s
```
scp -i keys keys root@192.168.122.200:

ssh -o StrictHostKeyChecking=no -i keys root@192.168.122.200

echo "alias kubectl='k8s kubectl'" >> /root/.bashrc
. /root/.bashrc
k8s bootstrap



TOKEN=$(k8s get-join-token --worker)
ssh -o StrictHostKeyChecking=no -i keys root@192.168.122.201  "k8s join-cluster $TOKEN"

TOKEN=$(k8s get-join-token --worker)
ssh -o StrictHostKeyChecking=no -i keys root@192.168.122.202  "k8s join-cluster $TOKEN"
```

### Test
```
kubectl get nodes
```

### Dashboard
```
kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
kubectl apply -f admin-user.yaml

kubectl -n kubernetes-dashboard create token admin-user


kubectl -n kubernetes-dashboard patch svc kubernetes-dashboard -p '{"spec": {"type": "NodePort"}}'
kubectl -n kubernetes-dashboard get svc
```


