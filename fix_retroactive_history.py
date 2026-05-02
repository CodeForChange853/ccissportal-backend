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

students = db.query(StudentProfile).filter(
    (StudentProfile.current_year_level > 1) | (StudentProfile.current_semester > 1)
).all()

first_faculty = db.query(FacultyProfile).first()
fallback_faculty_id = first_faculty.faculty_account_id if first_faculty else None

if not fallback_faculty_id:
    print("No faculty found.")
    exit(1)

fixed = 0
for student in students:
    entries_count = db.query(GradebookEntry).filter_by(student_account_id=student.student_account_id).count()
    if entries_count == 0:
        print(f"Fixing missing history for {student.first_name} {student.last_name}")

        course_name = student.current_course.upper()
        if "COMPUTER SCIENCE" in course_name:
            normalized_course = "BSCS"
        elif "INFORMATION TECHNOLOGY" in course_name:
            normalized_course = "BSIT"
        else:
            normalized_course = course_name

        historic_subs = db.query(CurriculumSubject).filter(
            (CurriculumSubject.target_year_level < student.current_year_level) |
            ((CurriculumSubject.target_year_level == student.current_year_level) & (CurriculumSubject.target_semester < student.current_semester))
        ).filter(CurriculumSubject.course == normalized_course).all()

        for subj in historic_subs:
            assigned = db.query(GradebookEntry).filter(
                GradebookEntry.curriculum_subject_id == subj.subject_id,
                GradebookEntry.student_account_id == None
            ).first()
            
            fac_id = assigned.faculty_account_id if assigned else fallback_faculty_id
            
            e = GradebookEntry(
                student_account_id=student.student_account_id,
                faculty_account_id=fac_id,
                curriculum_subject_id=subj.subject_id,
                midterm_grade=2.0,
                system_grade=2.0,
                final_grade=2.0,
                completion_status="PASSED"
            )
            db.add(e)
        fixed += 1

db.commit()
print(f"Fixed {fixed} students.")
