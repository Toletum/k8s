#!/bin/bash

source config

if [ ! -f ubuntu24.img ];
then
  wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img -O ubuntu24.img
else
  echo -e "${GREEN} ubuntu24.img before.${RESET}"
fi

echo -e "${GREEN} Generating ssh key.${RESET}"
rm -f keys keys.pub
ssh-keygen -t ed25519 -f keys -N "" -q
KEYSPUB=$(cat keys.pub)


if [ ! -f TEMPLATE.qcow2 ];
then
  echo -e "${GREEN} Creating TEMPLATE.qcow2.${RESET}"
qemu-img convert -f qcow2 -O qcow2 ubuntu24.img TEMPLATE.qcow2
qemu-img resize TEMPLATE.qcow2 +20G
else
  echo -e "${GREEN} TEMPLATE.qcow2 before.${RESET}"
fi

for key in "${!NODES[@]}"; do
echo -e "${GREEN} ${key}.qcow2 copying.${RESET}"
cp TEMPLATE.qcow2 ${key}.qcow2
done



for key in "${!NODES[@]}"; do

META_DATA="
instance-id: cluster
local-hostname: ${key}
"

USER_DATA="
#cloud-config
users:
  - name: root
    shell: /bin/bash
    ssh_authorized_keys:
      - ${KEYSPUB}

expire: false

ssh_pwauth: false
disable_root: false

write_files:
  - path: /etc/netplan/50-cloud-init.yaml
    content: |
      network:
        version: 2
        ethernets:
          enp1s0:
            dhcp4: false
            addresses:
              - ${NODES[$key]}/24
            routes:
              - to: 0.0.0.0/0
                via: 192.168.122.1
            nameservers:
              addresses:
                - 1.1.1.1
                - 8.8.8.8

runcmd:
  - apt update
  - apt upgrade -y
  - netplan apply
"


echo "$META_DATA" > meta-data-${key}

echo "$USER_DATA" > user-data-${key}

cloud-localds cloud-init-${key}.iso user-data-${key} meta-data-${key}

virt-install \
  --name ${key} \
  --ram=${MEMORY} \
  --vcpus=${CPUS} \
  --disk path=${key}.qcow2,format=qcow2 \
  --disk path=cloud-init-${key}.iso,device=cdrom \
  --os-variant ubuntu24.04 \
  --network bridge=virbr0,model=virtio \
  --import \
  --graphics none  > /dev/null 2>&1 &
done

for key in "${!NODES[@]}"; do
  ssh-keygen -f '/home/toletum/.ssh/known_hosts' -R ${NODES[$key]} > /dev/null 2>&1
  s=1
  while [ $s -ne 0 ]
  do
    echo -e "${YELLOW} ${key} waiting.${RESET}"
    ssh -o StrictHostKeyChecking=no -i keys root@${NODES[$key]} ls >/dev/null 2>&1
    s=$(echo $?)
  done
  echo -e "${GREEN} Node ${key} OK.${RESET}"
done



