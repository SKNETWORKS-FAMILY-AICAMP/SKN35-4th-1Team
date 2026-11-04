import pymysql

# Windows 용 mysqlclient 는 TiDB Cloud TLS 연결에 실패해서 PyMySQL 로 대신한다.
# Django 는 mysqlclient 2.2.1 이상을 요구하므로 버전만 맞춰 준다.
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()
