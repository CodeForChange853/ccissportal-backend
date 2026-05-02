# backend-v2/src/core/database_setup.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.core.config import settings

database_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   
    pool_size=10,         
    max_overflow=20,      
    pool_timeout=30,      
    pool_recycle=1800,    
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database_engine)

Base = declarative_base()

def get_database_session():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()