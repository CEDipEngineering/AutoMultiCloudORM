#!/bin/bash
cd /home/ubuntu
sudo apt update
sudo apt-get install python3-dev default-libmysqlclient-dev build-essential -y
git clone https://github.com/raulikeda/tasks.git
cd tasks
sed -i "s/node1/IPDB/g" ./portfolio/settings.py
sed -i "s/django.db.backends.postgresql/django.db.backends.mysql/g" ./portfolio/settings.py
sed -i "s/'USER': 'cloud'/'USER': 'root'/g" ./portfolio/settings.py
sed -i "s/5432/3306/g" ./portfolio/settings.py
echo "mysqlclient" >> requirements.txt
./install.sh
sudo reboot