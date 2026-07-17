# backend-v2/src/core/database_setup.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.core.config import settings

database_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,        # 5 base connections per worker — safe for Supabase free (60 conn cap)
    max_overflow=5,     # burst to 10 max; 2 Render workers = 20 total, leaves headroom
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