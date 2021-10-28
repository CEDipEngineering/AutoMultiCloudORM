ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'cloud';
CREATE USER 'root'@'%' IDENTIFIED BY 'cloud';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%';
FLUSH PRIVILEGES;
CREATE DATABASE tasks;