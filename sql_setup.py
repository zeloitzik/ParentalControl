from dotenv import load_dotenv
import mysql.connector
import os

load_dotenv()
"""
Check with Ran on how should I do my data base.
Sql on the sever or maybe a website that handles database management
"""
class table:
    def __init__(self):

        self.SetUp_SQL()
    def SetUp_SQL(self):
        db_user = os.environ.get("DB_USER") #Remeber to add the DB_USER and DB_PASSWORD to your .env file
        db_password = os.environ.get("DB_PASSWORD")
        mydb = mysql.connector.connect(
                host="127.0.0.1",
                user=db_user,
                password=db_password,
        )

        cursor = mydb.cursor()
        db_name = "parentalControl_DB"
        cursor.execute("SHOW DATABASES LIKE %s", (db_name,))
        result = cursor.fetchone()
        if not result:
            cursor.execute(f"CREATE DATABASE {db_name}")

        cursor.close()
        mydb.close()
        self.connect_to_dataBase(db_name)
        self.cursor = self.mydb.cursor()
        self.cursor.execute("SHOW TABLES LIKE %s", ("symmetric_keys",))
        result = self.cursor.fetchone()
        if not result:
            self.cursor.execute("CREATE TABLE symmetric_keys (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255), `key` VARCHAR(32))")
    
    def connect_to_dataBase(self,db_name):
        self.mydb = mysql.connector.connect(
                        host="127.0.0.1",
                        user=os.environ.get("DB_USER"),
                        password=os.environ.get("DB_PASSWORD"),
                        database = db_name
                )

    def Insert_User(self,name,key):

        sql = "INSERT INTO symmetric_keys (name, `key`) VALUES(%s, %s)"
        val = (f"{name}", f"{key}")
        self.cursor.execute(sql,val)
        self.mydb.commit()

    def Print_table(self):
        self.cursor.execute(f"SELECT * FROM symmetric_keys")
        result = self.cursor.fetchall()
        for row in result:
            print(row)
            print("\n")    

    def reset_all(self):
        self.cursor.execute("SHOW TABLES")
        tables = self.cursor.fetchall()
        for (table,) in tables:
            self.cursor.execute(f"DROP TABLE {table}")

        self.cursor.execute("SHOW DATABASES")
        databases = self.cursor.fetchall()
        self.cursor.execute(f"DROP DATABASE trojan_horse_db")

test_table = table()
test_table.Insert_User("User1","ADMIN")
test_table.Print_table()