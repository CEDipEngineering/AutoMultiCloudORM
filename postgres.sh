#!bin/bash
sudo apt update && sudo apt install postgresql postgresql-contrib -y
export PGPASSWORD='cloud'
echo "export PGPASSWORD='cloud'" >> $HOME/.bashrc
source $HOME/.bashrc
echo $PGPASSWORD
sudo -i -u postgres bash << EOF
createuser -s cloud -w
createdb -O cloud tasks
echo "listen_addresses = '*'" >> 12/main/postgresql.conf
echo "host all all 0.0.0.0/32 trust" >> 12/main/pg_hba.conf
EOF
sudo ufw allow 5432/tcp
sudo systemctl restart postgresql