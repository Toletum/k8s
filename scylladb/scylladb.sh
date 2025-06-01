# ScyllaDB in docker

source config

GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
RESET=$(tput sgr0)


echo -e "${YELLOW}🔧 Instalando Docker en paralelo...${RESET}"

for key in "${!NODES[@]}"; do
  {
    echo -e "${GREEN}▶ Nodo ${key} (${NODES[$key]})...${RESET}"

    ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} '
      apt update && apt upgrade -y
      apt-get install -y nfs-common qemu-guest-agent vim
      systemctl enable qemu-guest-agent
      systemctl start qemu-guest-agent
      snap install docker
      reboot
    ' >/dev/null 2>&1

    echo -e "${GREEN}✔ Nodo ${key} terminado.${RESET}"
  } &
done

wait
echo -e "${YELLOW}✅ Todos los nodos finalizados.${RESET}"



echo -e "${YELLOW}🔧 Nodes Uping....${RESET}"

for key in "${!NODES[@]}"; do
  ssh-keygen -f '/home/toletum/.ssh/known_hosts' -R ${NODES[$key]} > /dev/null 2>&1
  s=1
  while [ $s -ne 0 ]
  do
    echo -e "${GREEN}  ${key} intentando conexión...${RESET}"
    ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} ls || sleep 1 >/dev/null 2>&1
    s=$(echo $?)
  done
  echo -e "${GREEN}  ${key} OK${RESET}"
done


echo -e "${YELLOW}🔧 ScyllaDB Uping....${RESET}"
seeds=$(IFS=, ; echo "${NODES[*]}")
for key in "${!NODES[@]}"; do
ip="${NODES[$key]}"
hname="${key}"
ssh -t -o StrictHostKeyChecking=no -i keys root@${ip} "
docker volume create scylla-db-${hname}
docker run --restart unless-stopped -d --name scylla-${hname} \
  --hostname ${hname} \
  --network host \
  -v scylla-db-${hname}:/var/lib/scylla \
  scylladb/scylla \
  --seeds=\"${seeds}\" \
  --listen-address=${ip} \
  --broadcast-address=${ip} \
  --rpc-address=${ip} \
  --broadcast-rpc-address=${ip}
"
done
echo -e "${YELLOW}✅ SCYLLADB DONE.${RESET}"
exit

ssh -t -o StrictHostKeyChecking=no -i keys root@${NODES[node01]} docker exec -ti scylla-node01 nodetool status


ssh -t -o StrictHostKeyChecking=no -i keys root@${NODES[node01]} docker exec -ti scylla-node01 cqlsh


CREATE KEYSPACE my_keyspace WITH replication = { 'class': 'SimpleStrategy', 'replication_factor': 3 };
USE my_keyspace;
CREATE TABLE users (id UUID PRIMARY KEY, name TEXT, email TEXT);
INSERT INTO users (id, name, email) VALUES (uuid(), 'John Doe', 'john@example.com');
SELECT * FROM users;
exit


