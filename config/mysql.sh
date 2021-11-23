#!/bin/bash
sudo apt update && sudo apt install mysql-server -y
sudo mysql -uroot -e "SCRIPT_SQL"
echo "MYSQL_CONF" > /etc/mysql/mysql.conf.d/mysqld.cnf
sudo ufw allow 3306/tcp
sudo systemctl restart mysql