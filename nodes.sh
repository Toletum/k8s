#!/bin/bash

source colors
source config

if [ ! -f data/ubuntu24.img ]; then
#  wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img -O data/ubuntu24.img
#  wget https://cloud-images.ubuntu.com/oracular/current/oracular-server-cloudimg-amd64.img -O data/ubuntu24.img
  wget -O data/ubuntu24.img https://cloud-images.ubuntu.com/minimal/daily/oracular/current/oracular-minimal-cloudimg-amd64.img
else
  msg_warm "ubuntu24.img before"
fi

msg_warm "Generating ssh key."
rm -f data/keys data/keys.pub
ssh-keygen -t ed25519 -f data/keys -N "" -q


if [ ! -f data/TEMPLATE.qcow2 ]; then
  msg_warm "Creating TEMPLATE.qcow2"
  qemu-img convert -f qcow2 -O qcow2 data/ubuntu24.img data/TEMPLATE.qcow2
  qemu-img resize data/TEMPLATE.qcow2 +20G
else
  msg_warm "TEMPLATE.qcow2 before"
fi

for node in ${NODES_INI}; do
  {
  ./node.sh ${node}
  }&
done && wait

msg_ok "DONE"
