source config

if [ $# -ge 1 ]; then
  LABEL="$1"
else
  LABEL="XXX"
fi


for key in "${!NODES[@]}"; do
echo -e "${GREEN}Shutdowning ${key}...${RESET}"
virsh shutdown $key
done


for key in "${!NODES[@]}"; do
echo -e "${GREEN}Cloning ${key}...${RESET}"
virt-clone --original ${key} --auto-clone
virsh domrename ${key}-clone ${key}-${LABEL}
done

for key in "${!NODES[@]}"; do
echo -e "${GREEN}Starting ${key}...${RESET}"
virsh start $key
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

