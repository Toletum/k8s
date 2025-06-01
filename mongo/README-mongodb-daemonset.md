# MongoDB DaemonSet
```
source config

for key in "${!NODES[@]}"; do
ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} rm -rvf /data/db
done



for key in "${!NODES[@]}"; do
ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} mkdir -p /data/db
done


openssl rand -base64 756 > keyfile
scp -o StrictHostKeyChecking=no -i keys keyfile root@${NODES[$key]}:/data/db 

ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} '
chmod 400 /data/db/keyfile
chown 999:999 -R /data
'
done

kubectl apply -f mongo-daemonset.yaml

pending=1
while [ $pending -gt 0 ]; do
echo -e "${YELLOW} Waiting all nodes Ready... ${RESET}"
s=$(kubectl get pods -l app=mongo --no-headers | awk '{print "-",$3,"-"}')
sleep 1
pending=$(echo "$s" | grep -v " Running " | wc -l)
echo -e "${YELLOW} mongo pods no runnig: $pending... ${RESET}"
done
echo -e "${GREEN} mongo pods RUNNING ${RESET}"


POD=$(kubectl get pods -l app=mongo -o jsonpath='{.items[0].metadata.name}')


IPS=$(kubectl get pod -l app=mongo -o jsonpath="{range .items[*]}{.status.hostIP}{'\n'}{end}" | sort)

# Construir miembros
i=0
MEMBERS=""
for ip in $IPS; do
  MEMBERS+="    { _id: $i, host: \"$ip:27017\" },\n"
  ((i++))
done
MEMBERS=$(echo -e "$MEMBERS" | sed '$s/,\n$//')

SCRIPT=$(echo -e "rs.initiate({\n  _id: \"rs0\",\n  members: [\n$MEMBERS\n  ]\n});")

kubectl exec "$POD" -- mongosh --eval "$SCRIPT"


sleep 5

kubectl exec ${POD} -- mongosh -eval 'rs.status()'
```

## Admin User
```
PRIMARY=""
while [ "$PRIMARY" == "" ]; do
echo -e "${YELLOW} Waiting PRIMARY... ${RESET}"
PRIMARY=$(kubectl exec ${POD} -- sh -c "mongosh -eval 'rs.isMaster().primary' | cut -d":" -f1")
sleep 1
done
echo -e "${GREEN} PRIMARY ${PRIMARY} ${RESET}"

POD=$(kubectl get pods --field-selector status.podIP=${PRIMARY} -o jsonpath='{.items[0].metadata.name}')
echo -e "${GREEN} POD ${POD} ${RESET}"


kubectl exec $POD -- mongosh mongodb://127.0.0.1:27017/admin -eval '
db.createUser({
  user: "admin",
  pwd: "admin",  // Cambia esto por una contraseña segura
  roles: [{ role: "root", db: "admin" }]
});
'

```


## Test
```
kubectl exec $POD -- mongosh 'mongodb://admin:admin@127.0.0.1:27017/?directConnection=false&appName=mongosh+2.5.0&readPreference=primary'
```

## External Test
```
if [ ! -f ./mongosh-2.5.1-linux-x64/bin/mongosh ]; then
wget https://downloads.mongodb.com/compass/mongosh-2.5.1-linux-x64.tgz
tar xvf mongosh-2.5.1-linux-x64.tgz
fi

HOSTS=$(for ip in $IPS; do echo -n "$ip:27017,"; done | sed 's/,$//')

# String de conexión MongoDB
URI="mongodb://admin:admin@${HOSTS}/?directConnection=false&readPreference=primary"


./mongosh-2.5.1-linux-x64/bin/mongosh "$URI"
```

