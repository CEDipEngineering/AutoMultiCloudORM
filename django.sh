#!bin/bash
sudo apt update
git clone https://github.com/raulikeda/tasks.git
cd tasks
sed -i "s/node1/IPDB/g" ./portfolio/settings.py
./install.sh
sudo reboot