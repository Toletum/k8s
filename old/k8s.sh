#!/bin/bash

source colors

readarray -t NODES < <(virsh list --name)
MANAGER=${NODES[0]}
WORKERS=${NODES[@]:1}

msg "${GREEN}" "Getting IPs"
unset IPs
declare -A IPs
for NODE in ${NODES[@]}; do
  ip=$(virsh domifaddr "$NODE" | awk '/vnet/ {print $4}' | cut -d'/' -f1)
  IPs["$NODE"]=$ip
done
msg "${GREEN}" "IPs: ${IPs[@]}"


for NODE in ${NODES[@]}; do
  ./k8s_node.sh ${NODE} INSTALL
done

./k8s_node.sh ${MANAGER} MANAGER

for W in ${WORKERS[@]}; do
./k8s_node.sh ${W} WORKER "${IPs[$MANAGER]}"
done


exit

