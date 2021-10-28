#!/bin/bash
sudo apt update
git clone https://github.com/raulikeda/tasks.git
cd tasks
sed -i "s/node1/IPDB/g" ./portfolio/settings.py
sed -i "s/django.db.backends.postgresql/django.db.backends.mysql/g" ./portfolio/settings.py
sed -i "s/'USER': 'cloud'/'USER': 'root'/g" ./portfolio/settings.py
sed -i "s/5432/3306/g" ./portfolio/settings.py
./install.sh
sudo reboot