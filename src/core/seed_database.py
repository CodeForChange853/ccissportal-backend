import sys
import os
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.core.database_setup import SessionLocal, Base, database_engine
from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import (
    CurriculumSubject, StudentProfile,
)
from src.modules.faculty.models import FacultyProfile, GradebookEntry
from src.modules.settings.models import SystemSettings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 1. System Settings ─────────────────────────────────────────────────────

def _seed_settings(db: Session) -> None:
    if db.query(SystemSettings).filter(SystemSettings.settings_id == 1).first():
        print("  [SKIP] System settings already exist.")
        return

    db.add(SystemSettings(
        settings_id=1,
        is_enrollment_open=True,
        global_max_teaching_load=4,
        student_registration_passkey="CCIS2025",
    ))
    print("  [OK]   System settings seeded.  Passkey: CCIS2025")


# ── 2. Curriculum (49 subjects) ────────────────────────────────────────────

# (subject_code, subject_title, year, semester, credit_units, course)
SUBJECTS: list[tuple] = [
    # Year 1 — Semester 1
    ("ITE 1",     "Introduction to Computing",    1, 1, 3, "BSCS"),
    ("ITE 2",     "Computer Programming 1",        1, 1, 3, "BSCS"),
    ("CS 101",    "Discrete Structures 1",         1, 1, 3, "BSCS"),
    ("NSTP 1",    "CWTS 1",                        1, 1, 3, "COMMON"),
    ("GE 1",      "Understanding the Self",        1, 1, 3, "COMMON"),
    ("GE 2",      "Readings in Phil History",      1, 1, 3, "COMMON"),
    ("GE Elec 1", "Environmental Science",         1, 1, 3, "COMMON"),
    ("PATHFit 1", "Movement Competency",           1, 1, 2, "COMMON"),
    # Year 1 — Semester 2
    ("GE 3",      "Math in Modern World",          1, 2, 3, "COMMON"),
    ("GE 4",      "The Contemporary World",        1, 2, 3, "COMMON"),
    ("GE Elec 2", "Living in the IT Era",          1, 2, 3, "COMMON"),
    ("PATHFit 2", "Exercise-Based Fitness",        1, 2, 2, "COMMON"),
    ("NSTP 2",    "CWTS 2",                        1, 2, 3, "COMMON"),
    ("ITE 3",     "Data Structures",               1, 2, 3, "BSCS"),
    ("ITE 4",     "Computer Programming 2",        1, 2, 3, "BSCS"),
    ("CS 102",    "Discrete Structures 2",         1, 2, 3, "BSCS"),
    # Year 2 — Semester 1
    ("CS MATH",   "Math for CS",                   2, 1, 3, "BSCS"),
    ("GE 5",      "Purposive Communication",       2, 1, 3, "COMMON"),
    ("GE 6",      "Science, Tech, Society",        2, 1, 3, "COMMON"),
    ("CS 201",    "Algorithms and Complexity",     2, 1, 3, "BSCS"),
    ("CS 202",    "Object Oriented Prog",          2, 1, 3, "BSCS"),
    ("ITE 5",     "Information Management",        2, 1, 3, "BSCS"),
    ("PATHFit 3", "Dance/Sports 1",                2, 1, 2, "COMMON"),
    # Year 2 — Semester 2
    ("GE 7",      "Art Appreciation",              2, 2, 3, "COMMON"),
    ("GE 8",      "Ethics",                        2, 2, 3, "COMMON"),
    ("ITE 6",     "App Dev & Emerging Tech",       2, 2, 3, "BSCS"),
    ("CS 203",    "Architecture & Org",            2, 2, 3, "BSCS"),
    ("CS 204",    "Operating Systems",             2, 2, 3, "BSCS"),
    ("CS 205",    "HCI",                           2, 2, 3, "BSCS"),
    ("PATHFit 4", "Dance/Sports 2",                2, 2, 2, "COMMON"),
    # Year 3 — Semester 1
    ("CS 301",    "Programming Languages",         3, 1, 3, "BSCS"),
    ("CS 302",    "Automata Theory",               3, 1, 3, "BSCS"),
    ("CS 303",    "Software Engineering 1",        3, 1, 3, "BSCS"),
    ("CS Elec 1", "Professional Elective 1",       3, 1, 3, "BSCS"),
    ("GE Elec 3", "Reading Visual Art",            3, 1, 3, "COMMON"),
    # Year 3 — Semester 2
    ("CS 304",    "Software Engineering 2",        3, 2, 3, "BSCS"),
    ("CS 305",    "Social Issues",                 3, 2, 3, "BSCS"),
    ("CS 306",    "Multimedia",                    3, 2, 3, "BSCS"),
    ("CS Elec 2", "Professional Elective 2",       3, 2, 3, "BSCS"),
    ("CS Elec 3", "Professional Elective 3",       3, 2, 3, "BSCS"),
    # Year 3 — Summer
    ("CS 307",    "Practicum (240 Hours)",          3, 3, 3, "BSCS"),
    # Year 4 — Semester 1
    ("CS 401",    "CS Thesis Writing 1",           4, 1, 3, "BSCS"),
    ("CS 402",    "Networks & Comm",               4, 1, 3, "BSCS"),
    ("CS 403",    "Integrative Prog 1",            4, 1, 3, "BSCS"),
    ("CS 404",    "Data Mining 1",                 4, 1, 3, "BSCS"),
    ("GE 9",      "Rizal's Life and Works",        4, 1, 3, "COMMON"),
    # Year 4 — Semester 2
    ("CS 405",    "CS Thesis Writing 2",           4, 2, 3, "BSCS"),
    ("CS 406",    "Info Assurance & Sec",          4, 2, 3, "BSCS"),
    ("CS 407",    "Integrative Prog 2",            4, 2, 3, "BSCS"),
    ("CS 408",    "Data Mining 2",                 4, 2, 3, "BSCS"),
    ("CS 409",    "Advanced Algorithm",            4, 2, 3, "BSCS"),
]

# All 29 prerequisite relationships from the original curriculum graph.
# Format: { subject_code: prerequisite_code }
PREREQ_MAP: dict[str, str] = {
    # Year 1 Sem 2
    "PATHFit 2": "PATHFit 1",
    "NSTP 2":    "NSTP 1",
    "ITE 3":     "ITE 2",
    "ITE 4":     "ITE 2",
    "CS 102":    "CS 101",
    # Year 2 Sem 1
    "CS MATH":   "GE 3",
    "CS 201":    "ITE 3",
    "CS 202":    "ITE 4",
    "ITE 5":     "ITE 3",
    "PATHFit 3": "PATHFit 2",
    # Year 2 Sem 2
    "ITE 6":     "CS 202",
    "CS 203":    "CS 102",
    "CS 204":    "CS 203",
    "CS 205":    "ITE 5",
    "PATHFit 4": "PATHFit 3",
    # Year 3 Sem 1
    "CS 301":    "CS 201",
    "CS 302":    "CS 102",
    "CS 303":    "ITE 6",
    # Year 3 Sem 2
    "CS 304":    "CS 303",
    # Year 3 Summer
    "CS 307":    "CS 304",
    # Year 4 Sem 1
    "CS 401":    "CS 307",
    "CS 402":    "CS 204",
    "CS 403":    "CS 301",
    "CS 404":    "CS 201",
    # Year 4 Sem 2
    "CS 405":    "CS 401",
    "CS 406":    "CS 402",
    "CS 407":    "CS 403",
    "CS 408":    "CS 404",
    "CS 409":    "CS 201",
}


def _seed_curriculum(db: Session) -> None:
    if db.query(CurriculumSubject).count() > 0:
        print("  [SKIP] Curriculum already seeded.")
        return

    # Step A: Insert all subjects without prerequisites first
    for code, title, year, sem, units, course in SUBJECTS:
        db.add(CurriculumSubject(
            subject_code=code,
            subject_title=title,
            target_year_level=year,
            target_semester=sem,
            credit_units=units,
            course=course,
            prerequisite_subject_id=None,   # wired in Step B
        ))

    db.flush()   # get all subject_ids assigned before linking

    # Build a code → subject_id lookup
    code_to_id: dict[str, int] = {
        row.subject_code: row.subject_id
        for row in db.query(CurriculumSubject).all()
    }

    # Step B: Wire the 29 prerequisite relationships
    linked = 0
    for subject_code, prereq_code in PREREQ_MAP.items():
        subject = db.query(CurriculumSubject).filter(
            CurriculumSubject.subject_code == subject_code
        ).first()
        if subject and prereq_code in code_to_id:
            subject.prerequisite_subject_id = code_to_id[prereq_code]
            linked += 1

    print(f"  [OK]   {len(SUBJECTS)} subjects seeded, {linked} prerequisite links wired.")


# ── 3. Admin account ───────────────────────────────────────────────────────

def _seed_admin(db: Session) -> UserAccount:
    admin_email = "admin@university.edu"
    existing = db.query(UserAccount).filter(
        UserAccount.email_address == admin_email
    ).first()
    if existing:
        print("  [SKIP] Admin account already exists.")
        return existing

    admin = UserAccount(
        email_address=admin_email,
        hashed_password=pwd_context.hash("admin123"),
        account_role="ADMIN",
        is_active_account=True,
    )
    db.add(admin)
    db.flush()

    # Admin needs a FacultyProfile so the system can use them as a
    # grade-entry placeholder when assigning historical gradebook rows.
    db.add(FacultyProfile(
        faculty_account_id=admin.account_id,
        first_name="System",
        last_name="Administrator",
        academic_department="REGISTRAR",
        employee_id="ADMIN-001",
        maximum_teaching_load=0,     # admin doesn't teach
        current_teaching_load=0,
        is_available_for_classes=False,
    ))

    print("  [OK]   Admin account seeded.  admin@university.edu / admin123")
    return admin


# ── 4. Test student (3rd year, 2nd semester) ───────────────────────────────

# Subjects the student has PASSED: Year 1 Sem 1 → Year 3 Sem 1 (40 subjects)
PASSED_CODES = [
    # Year 1 Sem 1
    "ITE 1", "ITE 2", "CS 101", "NSTP 1", "GE 1", "GE 2", "GE Elec 1", "PATHFit 1",
    # Year 1 Sem 2
    "GE 3", "GE 4", "GE Elec 2", "PATHFit 2", "NSTP 2", "ITE 3", "ITE 4", "CS 102",
    # Year 2 Sem 1
    "CS MATH", "GE 5", "GE 6", "CS 201", "CS 202", "ITE 5", "PATHFit 3",
    # Year 2 Sem 2
    "GE 7", "GE 8", "ITE 6", "CS 203", "CS 204", "CS 205", "PATHFit 4",
    # Year 3 Sem 1
    "CS 301", "CS 302", "CS 303", "CS Elec 1", "GE Elec 3",
]

# Subjects the student is currently enrolled in: Year 3 Sem 2 (5 subjects)
CURRENT_CODES = [
    "CS 304", "CS 305", "CS 306", "CS Elec 2", "CS Elec 3",
]

# Sample final grades for passed subjects (realistic BSCS grades)
PASSED_GRADES: dict[str, tuple[float, float]] = {
    # (midterm, final)
    "ITE 1": (1.50, 1.50), "ITE 2": (1.25, 1.25), "CS 101": (1.50, 1.75),
    "NSTP 1": (1.00, 1.00), "GE 1": (1.25, 1.50), "GE 2": (1.50, 1.50),
    "GE Elec 1": (1.75, 1.75), "PATHFit 1": (1.25, 1.00),
    "GE 3": (1.75, 2.00), "GE 4": (1.50, 1.50), "GE Elec 2": (1.75, 1.75),
    "PATHFit 2": (1.25, 1.25), "NSTP 2": (1.00, 1.00),
    "ITE 3": (1.50, 1.75), "ITE 4": (1.25, 1.50), "CS 102": (1.75, 2.00),
    "CS MATH": (2.00, 2.00), "GE 5": (1.50, 1.25), "GE 6": (1.75, 1.75),
    "CS 201": (1.50, 1.75), "CS 202": (1.75, 1.75), "ITE 5": (2.00, 2.00),
    "PATHFit 3": (1.25, 1.25),
    "GE 7": (1.50, 1.25), "GE 8": (1.75, 1.50),
    "ITE 6": (1.75, 2.00), "CS 203": (2.00, 2.00), "CS 204": (2.25, 2.25),
    "CS 205": (1.75, 1.75), "PATHFit 4": (1.25, 1.00),
    "CS 301": (1.50, 1.75), "CS 302": (2.00, 2.00), "CS 303": (1.75, 1.75),
    "CS Elec 1": (2.25, 2.25), "GE Elec 3": (1.50, 1.50),
}

# Sample midterm grades for current subjects (final not yet entered)
CURRENT_MIDTERMS: dict[str, float] = {
    "CS 304": 1.75, "CS 305": 2.00, "CS 306": 2.25,
    "CS Elec 2": 2.50, "CS Elec 3": 2.00,
}


def _seed_test_student(db: Session, admin_account: UserAccount) -> None:
    student_email = "test.student@university.edu"
    if db.query(UserAccount).filter(
        UserAccount.email_address == student_email
    ).first():
        print("  [SKIP] Test student already exists.")
        return

    # Create auth account
    student = UserAccount(
        email_address=student_email,
        hashed_password=pwd_context.hash("student123"),
        account_role="STUDENT",
        is_active_account=True,
    )
    db.add(student)
    db.flush()

    # Create student profile
    db.add(StudentProfile(
        student_account_id=student.account_id,
        first_name="Juan",
        last_name="Test",
        student_number="2022-00001",
        current_course="BSCS",
        current_year_level=3,
        current_semester=2,          # 3rd year, 2nd semester
    ))

    db.flush()

    # Helper: get subject_id by code
    def get_sid(code: str) -> int | None:
        row = db.query(CurriculumSubject).filter(
            CurriculumSubject.subject_code == code
        ).first()
        return row.subject_id if row else None

    # PASSED subjects — full history from Year 1 Sem 1 → Year 3 Sem 1
    passed_count = 0
    for code in PASSED_CODES:
        sid = get_sid(code)
        if sid is None:
            print(f"  [WARN] Subject not found: {code}")
            continue
        midterm, final = PASSED_GRADES.get(code, (2.00, 2.00))
        db.add(GradebookEntry(
            student_account_id=student.account_id,
            faculty_account_id=admin_account.account_id,  # admin as placeholder
            curriculum_subject_id=sid,
            midterm_grade=midterm,
            final_grade=final,
            completion_status="PASSED",
        ))
        passed_count += 1

    # CURRENT subjects — Year 3 Sem 2 (in progress, midterm entered)
    current_count = 0
    for code in CURRENT_CODES:
        sid = get_sid(code)
        if sid is None:
            print(f"  [WARN] Subject not found: {code}")
            continue
        midterm = CURRENT_MIDTERMS.get(code, 2.00)
        db.add(GradebookEntry(
            student_account_id=student.account_id,
            faculty_account_id=admin_account.account_id,
            curriculum_subject_id=sid,
            midterm_grade=midterm,
            final_grade=None,
            completion_status="IN PROGRESS",
        ))
        current_count += 1

    print(
        f"  [OK]   Test student seeded.  test.student@university.edu / student123\n"
        f"         Year 3, Sem 2 | {passed_count} subjects PASSED | {current_count} IN PROGRESS"
    )


# ── Entrypoint ─────────────────────────────────────────────────────────────

def seed_database() -> None:
    # Ensure tables exist before seeding
    Base.metadata.create_all(bind=database_engine)
    
    db = SessionLocal()
    try:
        print("\n-- Seeding database (Phase 1 minimal) ------------------------")

        _seed_settings(db)
        _seed_curriculum(db)
        admin = _seed_admin(db)
        db.flush()
        _seed_test_student(db, admin)

        db.commit()

        print("\n[OK]  Seeding complete.")
        print("-------------------------------------------------------------")
        print("  Admin   -> admin@university.edu         / admin123")
        print("  Student -> test.student@university.edu  / student123")
        print("            3rd Year, 2nd Semester, BSCS")
        print("            40 subjects PASSED | 5 IN PROGRESS (3rd yr 2nd sem)")
        print("-------------------------------------------------------------\n")

    except Exception as err:
        print(f"\n[ERROR]  Seeding error: {err}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()