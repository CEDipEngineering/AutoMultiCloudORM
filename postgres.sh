sudo apt update && sudo apt install postgresql postgresql-contrib -y
sudo su - postgres
createuser -s cloud -W
createdb -O cloud tasks
sed -i "s/# listen_addresses = '*'/listen_addresses = '/g" /etc/postgresql/12/main/postgresql.conf
echo "host all all 0.0.0.0/32 trust" >> /etc/postgresql/12/main/pg_hba.conf
exit
sudo ufw allow 5432/tcp
sudo systemctl restart postgresql