import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import StudentProfile
from src.modules.faculty.models import GradebookEntry

# Get latest student
latest_student = db.query(StudentProfile).order_by(StudentProfile.profile_id.desc()).first()

if not latest_student:
    print("No students found.")
else:
    print(f"Latest Student: {latest_student.first_name} {latest_student.last_name}")
    print(f"Year Level: {latest_student.current_year_level}, Sem: {latest_student.current_semester}")

    # Check gradebook entries
    entries = db.query(GradebookEntry).filter(GradebookEntry.student_account_id == latest_student.student_account_id).all()
    print(f"Gradebook entries: {len(entries)}")
    for e in entries:
        print(f" - Subj: {e.curriculum_subject_id}, Grade: {e.final_grade}, Status: {e.completion_status}")

