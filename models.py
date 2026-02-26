from sqlalchemy import create_all, Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class Family(Base):
    __tablename__ = 'families'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    
    # קשר למשתמשים של המשפחה
    users = relationship("User", back_populates="family")

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    family_id = Column(Integer, ForeignKey('families.id'))
    name = Column(String)
    role = Column(String)  # למשל: 'admin', 'child'
    
    family = relationship("Family", back_populates="users")
    # קשר לסטטיסטיקה של המשתמש
    stats = relationship("Statistics", back_populates="user", uselist=False)

class Statistics(Base):
    __tablename__ = 'statistics'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    limit_minutes = Column(Integer, default=120)  # זמן מוקצב
    used_minutes = Column(Integer, default=0)     # זמן שנוצל
    
    user = relationship("User", back_populates="stats")

# יצירת בסיס הנתונים (במקרה זה SQLite מקומי)
# engine = create_engine('sqlite:///family_app.db')
# Base.metadata.create_all(engine)