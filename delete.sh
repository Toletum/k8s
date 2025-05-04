
source config

for key in "${!NODES[@]}"; do
#    echo "$key => ${NODES[$key]}"
virsh destroy "$key"
virsh undefine "$key" --remove-all-storage
done
clear
