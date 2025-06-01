
readarray -t NODES < <(virsh list --name)

for NODE in ${NODES[@]}; do
  virsh destroy "$NODE"
  virsh undefine "$NODE" --remove-all-storage
done
