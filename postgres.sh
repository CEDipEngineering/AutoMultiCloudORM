#!/bin/bash
sudo apt update && sudo apt install postgresql postgresql-contrib -y
echo "export PGPASSWORD='cloud'" >> /etc/environment
source /etc/environment
sudo -i -u postgres bash << EOF
createuser -s cloud -w
createdb -O cloud tasks
echo "listen_addresses = '*'" >>  /etc/postgresql/12/main/postgresql.conf
echo "host all all 0.0.0.0/0 trust" >>  /etc/postgresql/12/main/pg_hba.conf
EOF
sudo ufw allow 5432/tcp
sudo systemctl restart postgresql