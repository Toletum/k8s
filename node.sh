#!/bin/bash

source colors
source config

NODE="$1"

if [ "$NODE" == "" ]; then
  msg_error "NODE?"
  exit 1
fi

if [ ! -f data/TEMPLATE.qcow2 ]; then
  msg_error "TEMPLATE.qcow2?"
  exit 1
fi

msg_warm "${NODE}: ${NODE}.qcow2 copying..."
cp data/TEMPLATE.qcow2 data/${NODE}.qcow2
msg_ok "${NODE}: ${NODE}.qcow2 done"

KEYSPUB=$(cat data/keys.pub)

cat <<EOF > data/meta-data-${NODE}
instance-id: cluster
local-hostname: ${NODE}
EOF

cat <<EOF > data/user-data-${NODE}
#cloud-config
users:
  - name: root
    shell: /bin/bash
    ssh_authorized_keys:
      - ${KEYSPUB}

disable_root: false

write_files:
  - path: /etc/JCS
    permissions: '0644'
    owner: root:root
    content: |
      INI

runcmd:
  - echo "UPDATING..." > /etc/JCS
  - apt update
  - echo "UPGRADING..." > /etc/JCS
  - apt upgrade -y
  - echo "END" > /etc/JCS
  - reboot
EOF

process
cloud-localds data/cloud-init-${NODE}.iso data/user-data-${NODE} data/meta-data-${NODE}

rm -v data/user-data-${NODE} data/meta-data-${NODE}

virt-install \
  --name ${NODE} \
  --ram=4096 \
  --vcpus=4 \
  --disk path=data/${NODE}.qcow2,format=qcow2 \
  --disk path=data/cloud-init-${NODE}.iso,device=cdrom \
  --os-variant generic \
  --network network=default,model=virtio \
  --import \
  --graphics none  > /dev/null 2>&1 &
restore

msg_warm "${NODE}: waiting up & running..."
sleep 20

ip=""
while [ "$ip" == "" ]; do
  sleep 5
  msg_warm "${NODE}: waiting IP..."
  ip=$(getIP "$NODE")
done
msg_ok "${NODE}: $ip"

ssh-keygen -f "${HOME}/.ssh/known_hosts" -R ${ip} > /dev/null 2>&1

while true;
do
  STATUS=$($SSH root@${ip} cat /etc/JCS 2> /dev/null)
  if [ $? -ne 0 ]; then
    STATUS="NO SSH UP&RUNNING"
  fi
  if [ "$STATUS" == "END" ]; then
    break
  fi
  msg_warm "${NODE}: ${STATUS}"
  sleep 5
done
msg_ok "${NODE}: ${ip} OK"

