
ssh -i keys root@192.168.122.200

python -m venv .venv
source .venv/bin/activate

pip install kopf kubernetes


kubectl apply -f busyboxdaemon-crd.yaml


export KUBECONFIG=/home/toletum/k8s/kubeconfig
kopf run operator-bb.py --namespace=default


kubectl apply -f test-busy.yaml

