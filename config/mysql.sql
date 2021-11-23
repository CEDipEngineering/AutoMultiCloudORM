ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'cloud';
CREATE USER 'root'@'%' IDENTIFIED BY 'cloud';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%';
FLUSH PRIVILEGES;
CREATE DATABASE tasks;
CREATE TABLE tasks.user (id INT PRIMARY KEY, nome CHAR(40) NOT NULL, saldo FLOAT(16,2) DEFAULT 0.0);
INSERT INTO tasks.user VALUES (1, 'Sideshow Bob', 10.5), (2, 'Lisa Simpson', 520.30), (3, 'Homer Simpson', 0); 