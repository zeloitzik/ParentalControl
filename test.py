from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://postgres:itzik%402007@localhost:5432/warden_db"
)

connection = engine.connect()
print("Connected successfully!")
connection.close()