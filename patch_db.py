import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("No DATABASE_URL found.")
    exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE gradebook_entries ADD COLUMN system_grade FLOAT;"))
        conn.commit()
        print("Added system_grade column.")
    except Exception as e:
        print("system_grade might already exist:", e)

    try:
        conn.execute(text("ALTER TABLE gradebook_entries ADD COLUMN override_reason VARCHAR(500);"))
        conn.commit()
        print("Added override_reason column.")
    except Exception as e:
        print("override_reason might already exist:", e)
