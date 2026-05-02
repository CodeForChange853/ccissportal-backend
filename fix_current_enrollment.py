import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
db = sessionmaker(bind=create_engine(DATABASE_URL))()

from src.modules.enrollment.models import CurriculumSubject, StudentProfile
from src.modules.faculty.models import GradebookEntry, FacultyProfile
from src.modules.auth.models import UserAccount

students = db.query(StudentProfile).filter(StudentProfile.current_year_level > 1).all()
fac_id = db.query(FacultyProfile).first().faculty_account_id
fixed = 0

for student in students:
    course_name = student.current_course.upper()
    norm = "BSCS" if "COMPUTER SCIENCE" in course_name else ("BSIT" if "INFORMATION" in course_name else course_name)
    curr_subs = db.query(CurriculumSubject).filter_by(
        course=norm, 
        target_year_level=student.current_year_level, 
        target_semester=student.current_semester
    ).all()
    
    for s in curr_subs:
        if db.query(GradebookEntry).filter_by(student_account_id=student.student_account_id, curriculum_subject_id=s.subject_id).first() is None:
            a = db.query(GradebookEntry).filter_by(curriculum_subject_id=s.subject_id, student_account_id=None).first()
            assigned_fac = a.faculty_account_id if a else fac_id
            db.add(GradebookEntry(
                student_account_id=student.student_account_id, 
                faculty_account_id=assigned_fac, 
                curriculum_subject_id=s.subject_id, 
                completion_status="NOT STARTED"
            ))
            fixed += 1

db.commit()
print("Fixed current enrollment count:", fixed)
