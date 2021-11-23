#!/bin/bash
cd /home/ubuntu
sudo apt update
sudo apt-get install python3-dev default-libmysqlclient-dev build-essential -y
echo 'mysqlclient' > requirements.txt
echo 'flask-mysql' >> requirements.txt
echo 'cryptography' >> requirements.txt
sudo apt install python3-dev libpq-dev python3-pip -y
python3 -m pip install -r requirements.txt
git clone https://github.com/CEDipEngineering/basic-orm-example.git
mv basic-orm-example/orm.py ./
rm -rf basic-orm-example/
sed -i "<IP SUBSTITUTE>" ./orm.py
chmod +rx ./orm.py
sudo ufw allow 5000/tcp
echo '@reboot cd /home/ubuntu/ && python3 ./orm.py' | crontab
sudo reboot
