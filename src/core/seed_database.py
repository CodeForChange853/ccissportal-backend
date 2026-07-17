import sys
import os
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from datetime import datetime, timedelta, timezone, date as _date
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.core.database_setup import SessionLocal, Base, database_engine
from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import (
    CurriculumSubject, StudentProfile, StudentEnrollmentRequest,
)
from src.modules.faculty.models import (
    FacultyProfile, GradebookEntry, ConsultationSlot, ConsultationRequest,
)
from src.modules.settings.models import SystemSettings
from src.modules.support.models import SupportTicket, SystemAnnouncement
from src.modules.secretariat.models import (
    OJTSubmission, EquipmentInventory, EquipmentCheckout,
    CompletionRequest, SubjectMappingDraft, SubjectPetition,
    DocumentRequest, StudentOrganization, Facility, FacilityBooking,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
PW = pwd_context.hash("student123")   # all non-admin accounts

def _now(days_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)

def _date_ago(days_ago: int = 0) -> _date:
    return (_now(days_ago)).date()


# ─────────────────────────────────────────────────────────────────────────────
# 0.  WIPE — remove all non-admin data
# ─────────────────────────────────────────────────────────────────────────────

def _wipe(db: Session, admin_id: int) -> None:
    print("  [WIPE] Clearing all non-admin data…")
    db.query(FacilityBooking).delete(synchronize_session=False)
    db.query(StudentOrganization).delete(synchronize_session=False)
    db.query(DocumentRequest).delete(synchronize_session=False)
    db.query(SubjectPetition).delete(synchronize_session=False)
    db.query(SubjectMappingDraft).delete(synchronize_session=False)
    db.query(CompletionRequest).delete(synchronize_session=False)
    db.query(EquipmentCheckout).delete(synchronize_session=False)
    db.query(OJTSubmission).delete(synchronize_session=False)
    db.query(ConsultationRequest).delete(synchronize_session=False)
    db.query(ConsultationSlot).delete(synchronize_session=False)
    db.query(GradebookEntry).delete(synchronize_session=False)
    db.query(StudentEnrollmentRequest).delete(synchronize_session=False)
    db.query(StudentProfile).delete(synchronize_session=False)
    db.query(FacultyProfile).filter(
        FacultyProfile.faculty_account_id != admin_id
    ).delete(synchronize_session=False)
    db.query(SupportTicket).delete(synchronize_session=False)
    db.query(SystemAnnouncement).delete(synchronize_session=False)
    db.query(EquipmentInventory).delete(synchronize_session=False)
    db.query(Facility).delete(synchronize_session=False)
    db.query(UserAccount).filter(
        UserAccount.account_id != admin_id
    ).delete(synchronize_session=False)
    db.flush()
    print("  [WIPE] Done.")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  CURRICULUM  (49 BSCS subjects — kept from original)
# ─────────────────────────────────────────────────────────────────────────────

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

PREREQ_MAP: dict[str, str] = {
    "PATHFit 2": "PATHFit 1", "NSTP 2": "NSTP 1",
    "ITE 3": "ITE 2", "ITE 4": "ITE 2", "CS 102": "CS 101",
    "CS MATH": "GE 3", "CS 201": "ITE 3", "CS 202": "ITE 4",
    "ITE 5": "ITE 3", "PATHFit 3": "PATHFit 2",
    "ITE 6": "CS 202", "CS 203": "CS 102", "CS 204": "CS 203",
    "CS 205": "ITE 5", "PATHFit 4": "PATHFit 3",
    "CS 301": "CS 201", "CS 302": "CS 102", "CS 303": "ITE 6",
    "CS 304": "CS 303", "CS 307": "CS 304",
    "CS 401": "CS 307", "CS 402": "CS 204", "CS 403": "CS 301",
    "CS 404": "CS 201", "CS 405": "CS 401", "CS 406": "CS 402",
    "CS 407": "CS 403", "CS 408": "CS 404", "CS 409": "CS 201",
}

def _seed_curriculum(db: Session) -> None:
    if db.query(CurriculumSubject).count() > 0:
        print("  [SKIP] Curriculum already exists.")
        return
    for code, title, year, sem, units, course in SUBJECTS:
        db.add(CurriculumSubject(
            subject_code=code, subject_title=title,
            target_year_level=year, target_semester=sem,
            credit_units=units, course=course,
            prerequisite_subject_id=None,
        ))
    db.flush()
    code_to_id = {r.subject_code: r.subject_id for r in db.query(CurriculumSubject).all()}
    for code, prereq in PREREQ_MAP.items():
        subj = db.query(CurriculumSubject).filter(CurriculumSubject.subject_code == code).first()
        if subj and prereq in code_to_id:
            subj.prerequisite_subject_id = code_to_id[prereq]
    print(f"  [OK]   {len(SUBJECTS)} subjects + {len(PREREQ_MAP)} prereq links seeded.")


# ─────────────────────────────────────────────────────────────────────────────
# 2.  SYSTEM SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

def _seed_settings(db: Session) -> None:
    if db.query(SystemSettings).filter(SystemSettings.settings_id == 1).first():
        print("  [SKIP] System settings already exist.")
        return
    db.add(SystemSettings(
        settings_id=1,
        is_enrollment_open=True,
        global_max_teaching_load=4,
        student_registration_passkey="CCIS2025",
        wall_of_shame_cooldown_days=60,
    ))
    print("  [OK]   System settings seeded.  Passkey: CCIS2025")


# ─────────────────────────────────────────────────────────────────────────────
# 3.  ADMIN  (kept as-is; re-seeds FacultyProfile if missing)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_admin(db: Session) -> UserAccount:
    admin = db.query(UserAccount).filter(
        UserAccount.email_address == "admin@university.edu"
    ).first()
    if not admin:
        admin = UserAccount(
            email_address="admin@university.edu",
            hashed_password=pwd_context.hash("admin123"),
            account_role="ADMIN",
            is_active_account=True,
        )
        db.add(admin)
        db.flush()
        print("  [OK]   Admin account created.")
    else:
        print("  [KEEP] Admin account preserved.")

    if not db.query(FacultyProfile).filter(
        FacultyProfile.faculty_account_id == admin.account_id
    ).first():
        db.add(FacultyProfile(
            faculty_account_id=admin.account_id,
            first_name="System", last_name="Administrator",
            academic_department="REGISTRAR", employee_id="ADMIN-001",
            maximum_teaching_load=0, current_teaching_load=0,
            is_available_for_classes=False,
        ))
        db.flush()
    return admin


# ─────────────────────────────────────────────────────────────────────────────
# 4.  SECRETARY
# ─────────────────────────────────────────────────────────────────────────────

def _seed_secretary(db: Session) -> UserAccount:
    sec = UserAccount(
        email_address="secretary@university.edu",
        hashed_password=PW,
        account_role="SECRETARY",
        is_active_account=True,
    )
    db.add(sec)
    db.flush()
    print("  [OK]   Secretary: secretary@university.edu / student123")
    return sec


# ─────────────────────────────────────────────────────────────────────────────
# 5.  FACULTY  (4 instructors)
# ─────────────────────────────────────────────────────────────────────────────

FACULTY_DATA = [
    # (email, first, last, dept, emp_id, max_load, current_load, specialization)
    ("dr.santos@faculty.university.edu",   "Ricardo",  "Santos",   "CCIS", "FAC-0001", 4, 2, "Programming,Algorithms,Software Engineering"),
    ("prof.delacruz@faculty.university.edu","Maria",   "Dela Cruz","CCIS", "FAC-0002", 4, 3, "Discrete Mathematics,Theory of Computation,Algorithms"),
    ("dr.reyes@faculty.university.edu",    "Antonio",  "Reyes",    "CCIS", "FAC-0003", 4, 3, "Operating Systems,Computer Architecture,Networks"),
    ("prof.torres@faculty.university.edu", "Elena",    "Torres",   "GE",   "FAC-0004", 4, 1, "Technical Writing,Social Sciences,Ethics"),
]

def _seed_faculty(db: Session) -> list[UserAccount]:
    accounts = []
    for email, first, last, dept, emp_id, max_load, curr_load, specs in FACULTY_DATA:
        u = UserAccount(
            email_address=email, hashed_password=PW,
            account_role="FACULTY", is_active_account=True,
        )
        db.add(u); db.flush()
        db.add(FacultyProfile(
            faculty_account_id=u.account_id,
            first_name=first, last_name=last,
            academic_department=dept, employee_id=emp_id,
            maximum_teaching_load=max_load,
            current_teaching_load=curr_load,
            is_available_for_classes=curr_load < max_load,
            specialization_tags=specs,
            performance_score=round(85 + (hash(email) % 15), 1),
        ))
        accounts.append(u)
        print(f"  [OK]   Faculty: {email} / student123  ({first} {last})")
    db.flush()
    return accounts


# ─────────────────────────────────────────────────────────────────────────────
# 6.  STUDENTS  (8 students across all year levels)
# ─────────────────────────────────────────────────────────────────────────────

STUDENT_DATA = [
    # (email, first, last, stud_num, course, yr, sem, is_irregular)
    ("juan.santos@student.university.edu",     "Juan",     "Santos",   "2024-00001", "BSCS", 1, 1, False),
    ("maria.cruz@student.university.edu",      "Maria",    "Cruz",     "2024-00002", "BSCS", 1, 2, False),
    ("carlos.reyes@student.university.edu",    "Carlos",   "Reyes",    "2023-00010", "BSCS", 2, 1, False),
    ("ana.garcia@student.university.edu",      "Ana",      "Garcia",   "2023-00011", "BSCS", 2, 2, True),
    ("miguel.torres@student.university.edu",   "Miguel",   "Torres",   "2022-00020", "BSCS", 3, 1, False),
    ("sophia.lim@student.university.edu",      "Sophia",   "Lim",      "2022-00021", "BSCS", 3, 2, False),
    ("jose.mendoza@student.university.edu",    "Jose",     "Mendoza",  "2021-00030", "BSCS", 4, 1, False),
    ("isabella.santos@student.university.edu", "Isabella", "Santos",   "2021-00031", "BSCS", 4, 2, False),
]

def _seed_students(db: Session) -> dict[str, UserAccount]:
    accounts = {}
    for email, first, last, snum, course, yr, sem, irregular in STUDENT_DATA:
        u = UserAccount(
            email_address=email, hashed_password=PW,
            account_role="STUDENT", is_active_account=True,
        )
        db.add(u); db.flush()
        db.add(StudentProfile(
            student_account_id=u.account_id,
            first_name=first, last_name=last,
            student_number=snum,
            current_course=course,
            current_year_level=yr,
            current_semester=sem,
            is_irregular=irregular,
            ojt_clearance_status="NOT_REQUIRED" if yr < 3 else ("CLEARED" if yr >= 4 else "PENDING"),
        ))
        accounts[email] = u
        print(f"  [OK]   Student: {email} / student123  ({first} {last}, Yr{yr} Sem{sem})")
    db.flush()
    return accounts


# ─────────────────────────────────────────────────────────────────────────────
# 7.  ENROLLMENT REQUESTS
# ─────────────────────────────────────────────────────────────────────────────

def _seed_enrollments(db: Session, students: dict) -> None:
    # (email, yr, sem, status, cor_status, days_ago, notes)
    ENROLL_DATA = [
        ("juan.santos@student.university.edu",     1, 1, "PENDING",  "PENDING",  3,  None),
        ("maria.cruz@student.university.edu",      1, 2, "APPROVED", "RELEASED", 60, "All documents verified."),
        ("carlos.reyes@student.university.edu",    2, 1, "APPROVED", "RELEASED", 90, "AI-verified enrollment."),
        ("ana.garcia@student.university.edu",      2, 2, "APPROVED", "PENDING",  45, "Irregular track approved."),
        ("miguel.torres@student.university.edu",   3, 1, "APPROVED", "RELEASED", 120,"Complete documents submitted."),
        ("sophia.lim@student.university.edu",      3, 2, "APPROVED", "RELEASED", 150,"Enrollment approved."),
        ("jose.mendoza@student.university.edu",    4, 1, "APPROVED", "RELEASED", 180,"Thesis enrollment confirmed."),
        ("isabella.santos@student.university.edu", 4, 2, "APPROVED", "RELEASED", 210,"Final semester approved."),
    ]
    # Map subject codes to year/sem for building extracted_subjects lists
    yr_sem_codes: dict[tuple, list] = {}
    for code, _, yr, sem, _, _ in SUBJECTS:
        key = (yr, sem)
        yr_sem_codes.setdefault(key, []).append(code)

    for email, yr, sem, status, cor_status, days_ago, notes in ENROLL_DATA:
        u = students[email]
        subjects = yr_sem_codes.get((yr, sem), [])
        released_at = _now(days_ago - 5) if cor_status == "RELEASED" else None
        db.add(StudentEnrollmentRequest(
            student_account_id=u.account_id,
            target_year_level=yr,
            target_semester=sem,
            extracted_subjects=subjects,
            review_status=status,
            admin_review_notes=notes,
            date_submitted=_now(days_ago),
            cor_release_status=cor_status,
            cor_released_at=released_at,
        ))
    db.flush()
    print("  [OK]   8 enrollment requests seeded.")


# ─────────────────────────────────────────────────────────────────────────────
# 8.  GRADEBOOK ENTRIES
# ─────────────────────────────────────────────────────────────────────────────

# Grade sets: subject_code → (midterm, final) for PASSED
GRADE_POOL = {
    "ITE 1":     (1.50, 1.50), "ITE 2":     (1.25, 1.25), "CS 101":    (1.50, 1.75),
    "NSTP 1":    (1.00, 1.00), "GE 1":      (1.25, 1.50), "GE 2":      (1.50, 1.50),
    "GE Elec 1": (1.75, 1.75), "PATHFit 1": (1.25, 1.00),
    "GE 3":      (1.75, 2.00), "GE 4":      (1.50, 1.50), "GE Elec 2": (1.75, 1.75),
    "PATHFit 2": (1.25, 1.25), "NSTP 2":    (1.00, 1.00),
    "ITE 3":     (1.50, 1.75), "ITE 4":     (1.25, 1.50), "CS 102":    (1.75, 2.00),
    "CS MATH":   (2.00, 2.00), "GE 5":      (1.50, 1.25), "GE 6":      (1.75, 1.75),
    "CS 201":    (1.50, 1.75), "CS 202":    (1.75, 1.75), "ITE 5":     (2.00, 2.00),
    "PATHFit 3": (1.25, 1.25),
    "GE 7":      (1.50, 1.25), "GE 8":      (1.75, 1.50),
    "ITE 6":     (1.75, 2.00), "CS 203":    (2.00, 2.00), "CS 204":    (2.25, 2.25),
    "CS 205":    (1.75, 1.75), "PATHFit 4": (1.25, 1.00),
    "CS 301":    (1.50, 1.75), "CS 302":    (2.00, 2.00), "CS 303":    (1.75, 1.75),
    "CS Elec 1": (2.25, 2.25), "GE Elec 3": (1.50, 1.50),
    "CS 304":    (1.75, 1.75), "CS 305":    (2.00, 2.00), "CS 306":    (2.25, 2.00),
    "CS Elec 2": (2.00, 2.00), "CS Elec 3": (2.25, 2.25),
    "CS 307":    (1.50, 1.50),
    "CS 401":    (1.75, 1.75), "CS 402":    (2.00, 2.00), "CS 403":    (1.75, 1.75),
    "CS 404":    (2.00, 2.00), "GE 9":      (1.50, 1.50),
    "CS 405":    (1.75, 1.75), "CS 406":    (2.00, 2.00), "CS 407":    (1.75, 1.75),
    "CS 408":    (2.00, 2.00), "CS 409":    (2.25, 2.25),
}

# midterm-only (in progress)
MIDTERM_POOL = {
    "CS 304": 1.75, "CS 305": 2.00, "CS 306": 2.25, "CS Elec 2": 2.50, "CS Elec 3": 2.00,
    "CS 301": 2.00, "CS 302": 2.25, "CS 303": 1.75, "CS Elec 1": 2.50, "GE Elec 3": 1.75,
    "CS 401": 1.75, "CS 402": 2.00, "CS 403": 1.75, "CS 404": 2.00, "GE 9": 1.50,
    "CS MATH": 2.00, "GE 5": 1.75, "GE 6": 1.75, "CS 201": 1.75, "CS 202": 2.00, "ITE 5": 2.25, "PATHFit 3": 1.25,
    "GE 7": 1.50, "GE 8": 1.75, "ITE 6": 2.00, "CS 203": 2.00, "CS 205": 1.75, "PATHFit 4": 1.25,
}

def _codes_for_range(up_to_year: int, up_to_sem: int) -> list[str]:
    """Return all subject codes for year/sem ranges strictly before the given point."""
    result = []
    for code, _, yr, sem, _, _ in SUBJECTS:
        if yr < up_to_year or (yr == up_to_year and sem < up_to_sem):
            result.append(code)
    return result

def _codes_for_exact(year: int, sem: int) -> list[str]:
    return [code for code, _, yr, s, _, _ in SUBJECTS if yr == year and s == sem]

def _seed_gradebook(
    db: Session,
    students: dict,
    faculty: list[UserAccount],
    admin: UserAccount,
) -> dict[str, int]:
    """Returns mapping email → grade_id of the INC entry for Sophia (for CompletionRequest)."""
    code_to_id = {r.subject_code: r.subject_id for r in db.query(CurriculumSubject).all()}

    # Faculty assignment by subject domain
    def pick_faculty(code: str) -> int:
        if code.startswith("GE") or code.startswith("PATHFit") or code.startswith("NSTP"):
            return faculty[3].account_id   # Torres — GE dept
        if code in ("CS MATH", "CS 101", "CS 102", "CS 201", "CS 202", "CS 302", "CS 404", "CS 408", "CS 409"):
            return faculty[1].account_id   # Dela Cruz — Math/Theory
        if code in ("CS 203", "CS 204", "CS 402", "CS 406"):
            return faculty[2].account_id   # Reyes — Systems
        return faculty[0].account_id       # Santos — Programming/SE

    inc_grade_id = None
    total = 0

    # ── Maria Cruz: Year 1 Sem 1 passed, currently in Yr1 Sem2
    for code in _codes_for_exact(1, 1):
        sid = code_to_id.get(code)
        if sid:
            mid, fin = GRADE_POOL.get(code, (2.00, 2.00))
            db.add(GradebookEntry(
                student_account_id=students["maria.cruz@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=fin,
                completion_status="PASSED",
            ))
            total += 1
    for code in _codes_for_exact(1, 2):
        sid = code_to_id.get(code)
        if sid:
            mid = MIDTERM_POOL.get(code, 2.00)
            db.add(GradebookEntry(
                student_account_id=students["maria.cruz@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=None,
                completion_status="IN PROGRESS",
            ))
            total += 1

    # ── Carlos Reyes: Yr1 both sems passed, currently in Yr2 Sem1
    for code in _codes_for_range(2, 1):
        sid = code_to_id.get(code)
        if sid:
            mid, fin = GRADE_POOL.get(code, (2.00, 2.00))
            db.add(GradebookEntry(
                student_account_id=students["carlos.reyes@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=fin,
                completion_status="PASSED",
            ))
            total += 1
    for code in _codes_for_exact(2, 1):
        sid = code_to_id.get(code)
        if sid:
            mid = MIDTERM_POOL.get(code, 2.00)
            db.add(GradebookEntry(
                student_account_id=students["carlos.reyes@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=None,
                completion_status="IN PROGRESS",
            ))
            total += 1

    # ── Ana Garcia: Yr1+2 Sem1 passed (irregular — missing some Yr2 Sem2), currently Yr2 Sem2
    for code in _codes_for_range(2, 2):
        sid = code_to_id.get(code)
        if sid:
            mid, fin = GRADE_POOL.get(code, (2.00, 2.00))
            db.add(GradebookEntry(
                student_account_id=students["ana.garcia@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=fin,
                completion_status="PASSED",
            ))
            total += 1
    for code in _codes_for_exact(2, 2):
        sid = code_to_id.get(code)
        if sid:
            mid = MIDTERM_POOL.get(code, 2.00)
            db.add(GradebookEntry(
                student_account_id=students["ana.garcia@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=None,
                completion_status="IN PROGRESS",
            ))
            total += 1

    # ── Miguel Torres: Yr1-2 all sems passed, currently in Yr3 Sem1
    for code in _codes_for_range(3, 1):
        sid = code_to_id.get(code)
        if sid:
            mid, fin = GRADE_POOL.get(code, (2.00, 2.00))
            db.add(GradebookEntry(
                student_account_id=students["miguel.torres@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=fin,
                completion_status="PASSED",
            ))
            total += 1
    for code in _codes_for_exact(3, 1):
        sid = code_to_id.get(code)
        if sid:
            mid = MIDTERM_POOL.get(code, 2.00)
            db.add(GradebookEntry(
                student_account_id=students["miguel.torres@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=None,
                completion_status="IN PROGRESS",
            ))
            total += 1

    # ── Sophia Lim: Yr1-3 Sem1 passed, currently Yr3 Sem2; has INC on CS 204
    sophia_id = students["sophia.lim@student.university.edu"].account_id
    for code in _codes_for_range(3, 2):
        sid = code_to_id.get(code)
        if sid:
            if code == "CS 204":
                # INC grade — did not complete final
                entry = GradebookEntry(
                    student_account_id=sophia_id,
                    faculty_account_id=pick_faculty(code),
                    curriculum_subject_id=sid,
                    midterm_grade=2.25, final_grade=None,
                    completion_status="INC",
                )
                db.add(entry); db.flush()
                inc_grade_id = entry.grade_id
            else:
                mid, fin = GRADE_POOL.get(code, (2.00, 2.00))
                db.add(GradebookEntry(
                    student_account_id=sophia_id,
                    faculty_account_id=pick_faculty(code),
                    curriculum_subject_id=sid, midterm_grade=mid, final_grade=fin,
                    completion_status="PASSED",
                ))
            total += 1
    for code in _codes_for_exact(3, 2):
        sid = code_to_id.get(code)
        if sid:
            mid = MIDTERM_POOL.get(code, 2.00)
            db.add(GradebookEntry(
                student_account_id=sophia_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=None,
                completion_status="IN PROGRESS",
            ))
            total += 1

    # ── Jose Mendoza: Yr1-3 all sems + Summer passed, currently Yr4 Sem1
    for code in _codes_for_range(4, 1):
        sid = code_to_id.get(code)
        if sid:
            mid, fin = GRADE_POOL.get(code, (2.00, 2.00))
            db.add(GradebookEntry(
                student_account_id=students["jose.mendoza@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=fin,
                completion_status="PASSED",
            ))
            total += 1
    for code in _codes_for_exact(4, 1):
        sid = code_to_id.get(code)
        if sid:
            mid = MIDTERM_POOL.get(code, 2.00)
            db.add(GradebookEntry(
                student_account_id=students["jose.mendoza@student.university.edu"].account_id,
                faculty_account_id=pick_faculty(code),
                curriculum_subject_id=sid, midterm_grade=mid, final_grade=None,
                completion_status="IN PROGRESS",
            ))
            total += 1

    # ── Isabella Santos: All semesters up to and including Yr4 Sem2 (graduating)
    for code, _, yr, sem, _, _ in SUBJECTS:
        sid = code_to_id.get(code)
        if not sid:
            continue
        mid, fin = GRADE_POOL.get(code, (2.00, 2.00))
        db.add(GradebookEntry(
            student_account_id=students["isabella.santos@student.university.edu"].account_id,
            faculty_account_id=pick_faculty(code),
            curriculum_subject_id=sid, midterm_grade=mid, final_grade=fin,
            completion_status="PASSED",
        ))
        total += 1

    db.flush()
    print(f"  [OK]   {total} gradebook entries seeded  (1 INC for Sophia on CS 204).")
    return inc_grade_id


# ─────────────────────────────────────────────────────────────────────────────
# 9.  SECRETARIAT DATA
# ─────────────────────────────────────────────────────────────────────────────

def _seed_facilities(db: Session) -> list[Facility]:
    items = [
        Facility(facility_code="LAB-301", facility_name="Computer Laboratory 301",
                 facility_type="LAB", building="CCIS Building", capacity=40, is_bookable=True,
                 description="40-unit computer lab with high-speed internet and dual monitors."),
        Facility(facility_code="LAB-302", facility_name="Computer Laboratory 302",
                 facility_type="LAB", building="CCIS Building", capacity=40, is_bookable=True,
                 description="Programming lab with GPU workstations for graphics and ML courses."),
        Facility(facility_code="ROOM-201", facility_name="Lecture Room 201",
                 facility_type="ROOM", building="CCIS Building", capacity=50, is_bookable=True,
                 description="Standard lecture room with projector and whiteboard."),
        Facility(facility_code="SEM-101", facility_name="Seminar Room 101",
                 facility_type="ROOM", building="CCIS Building", capacity=25, is_bookable=True,
                 description="Small seminar room ideal for group discussions and presentations."),
        Facility(facility_code="AUD-1", facility_name="CCIS Auditorium",
                 facility_type="AUDITORIUM", building="CCIS Building", capacity=200, is_bookable=True,
                 description="Main auditorium for department-wide events and orientations."),
    ]
    for f in items:
        db.add(f)
    db.flush()
    print(f"  [OK]   {len(items)} facilities seeded.")
    return items


def _seed_equipment(db: Session, students: dict, faculty: list) -> None:
    proj = EquipmentInventory(
        asset_tag="PROJ-001", equipment_name="Epson EB-2265U Projector",
        category="HARDWARE", quantity_total=3, quantity_available=2,
        description="Full HD ultra-bright projector for classrooms.", is_active=True,
    )
    lap1 = EquipmentInventory(
        asset_tag="LAP-TEACH-001", equipment_name="Dell Latitude Teaching Laptop",
        category="HARDWARE", quantity_total=5, quantity_available=4,
        description="Faculty teaching laptop pre-loaded with course software.", is_active=True,
    )
    vr = EquipmentInventory(
        asset_tag="VR-001", equipment_name="Meta Quest 3 VR Headset",
        category="VR", quantity_total=4, quantity_available=3,
        description="VR headsets for HCI and immersive learning demonstrations.", is_active=True,
    )
    sw = EquipmentInventory(
        asset_tag="NET-SW-001", equipment_name="Cisco Catalyst 2960 Switch",
        category="NETWORKING", quantity_total=2, quantity_available=2,
        description="Managed 24-port switch for networking lab exercises.", is_active=True,
    )
    lap2 = EquipmentInventory(
        asset_tag="LAP-LOAN-001", equipment_name="HP ProBook Student Loanee Laptop",
        category="HARDWARE", quantity_total=10, quantity_available=8,
        description="Student loanee laptops for underserved enrolled students.", is_active=True,
    )
    for item in [proj, lap1, vr, sw, lap2]:
        db.add(item)
    db.flush()

    # 2 active checkouts
    db.add(EquipmentCheckout(
        equipment_id=lap2.id,
        borrower_account_id=students["jose.mendoza@student.university.edu"].account_id,
        borrower_type="STUDENT",
        checked_out_at=_now(10),
        expected_return_at=_now(-7),
        status="CHECKED_OUT",
        checkout_notes="Thesis work — approved by Dr. Santos.",
    ))
    db.add(EquipmentCheckout(
        equipment_id=proj.id,
        borrower_account_id=faculty[0].account_id,
        borrower_type="FACULTY",
        checked_out_at=_now(3),
        expected_return_at=_now(-4),
        status="CHECKED_OUT",
        checkout_notes="Needed for SE1 class presentation.",
    ))
    db.flush()
    print("  [OK]   5 equipment items + 2 active checkouts seeded.")


def _seed_ojt(db: Session, students: dict, sec: UserAccount) -> None:
    # Miguel — PENDING (just submitted)
    db.add(OJTSubmission(
        student_account_id=students["miguel.torres@student.university.edu"].account_id,
        moa_document_ref="uploads/ojt/moa_miguel_2022-00020.pdf",
        consent_form_ref="uploads/ojt/consent_miguel_2022-00020.pdf",
        medical_clearance_ref="uploads/ojt/medical_miguel_2022-00020.pdf",
        additional_notes="OJT at TechCorp Philippines, Cebu City. Duration: June–August 2025.",
        submission_status="PENDING",
        submitted_at=_now(2),
    ))
    # Sophia — VERIFIED (cleared by secretary)
    db.add(OJTSubmission(
        student_account_id=students["sophia.lim@student.university.edu"].account_id,
        moa_document_ref="uploads/ojt/moa_sophia_2022-00021.pdf",
        consent_form_ref="uploads/ojt/consent_sophia_2022-00021.pdf",
        medical_clearance_ref="uploads/ojt/medical_sophia_2022-00021.pdf",
        additional_notes="OJT completed at NexSystems Inc. All 240 hours rendered.",
        submission_status="VERIFIED",
        secretary_notes="All documents valid and complete. OJT cleared.",
        verified_by_secretary_id=sec.account_id,
        verified_at=_now(30),
        submitted_at=_now(45),
    ))
    db.flush()
    print("  [OK]   2 OJT submissions seeded (1 PENDING, 1 VERIFIED).")


def _seed_completion_request(db: Session, students: dict, sec: UserAccount, inc_grade_id: int) -> None:
    if inc_grade_id is None:
        print("  [SKIP] No INC grade id — skipping completion request.")
        return
    db.add(CompletionRequest(
        student_account_id=students["sophia.lim@student.university.edu"].account_id,
        gradebook_entry_id=inc_grade_id,
        workflow_state="PENDING_FEE",
        created_at=_now(5),
        workflow_notes=[{
            "actor_id": students["sophia.lim@student.university.edu"].account_id,
            "actor_role": "STUDENT",
            "state": "PENDING_FEE",
            "note": "Requesting completion exam for CS 204 — Operating Systems.",
            "ts": _now(5).isoformat(),
        }],
    ))
    db.flush()
    print("  [OK]   1 INC completion request seeded (Sophia -> CS 204, PENDING_FEE).")


def _seed_mapping_drafts(db: Session, students: dict, sec: UserAccount) -> None:
    # Carlos transferred from BSIT — secretary prepared a mapping draft
    db.add(SubjectMappingDraft(
        student_account_id=students["carlos.reyes@student.university.edu"].account_id,
        prepared_by_secretary_id=sec.account_id,
        previous_institution="Cebu Institute of Technology – University",
        previous_program="Bachelor of Science in Information Technology",
        mapping_entries=[
            {"previous_subject_code": "IT 111", "previous_subject_name": "Introduction to Programming",
             "previous_credit_units": 3, "ccis_subject_id": None, "recommended_action": "CREDIT"},
            {"previous_subject_code": "IT 112", "previous_subject_name": "Fundamentals of Database",
             "previous_credit_units": 3, "ccis_subject_id": None, "recommended_action": "VALIDATE"},
            {"previous_subject_code": "IT 211", "previous_subject_name": "Object Oriented Programming",
             "previous_credit_units": 3, "ccis_subject_id": None, "recommended_action": "CREDIT"},
        ],
        status="DRAFT",
        created_at=_now(7),
    ))
    db.flush()
    print("  [OK]   1 subject mapping draft seeded (Carlos Reyes — BSIT transfer).")


def _seed_petitions(db: Session, students: dict, sec: UserAccount) -> None:
    code_to_id = {r.subject_code: r.subject_id for r in db.query(CurriculumSubject).all()}

    # Ana Garcia — OVERLOAD petition (PENDING)
    db.add(SubjectPetition(
        student_account_id=students["ana.garcia@student.university.edu"].account_id,
        petition_type="OVERLOAD",
        subject_id=code_to_id["CS 205"],
        reason="I need to take CS 205 (HCI) this semester alongside my regular load to avoid further delays in my irregular track. My cumulative GWA is 1.85 and I have no failing grades.",
        status="PENDING",
        created_at=_now(4),
    ))
    # Maria Cruz — LATE_ADD petition (SECRETARY_ENDORSED → awaiting admin)
    db.add(SubjectPetition(
        student_account_id=students["maria.cruz@student.university.edu"].account_id,
        petition_type="LATE_ADD",
        subject_id=code_to_id["GE 4"],
        reason="I was unable to enroll in GE 4 during the regular enrollment period due to a system error. My enrollment form timed out and I lost my slot.",
        status="SECRETARY_ENDORSED",
        secretary_notes="Verified enrollment system error reported on the same date. Recommending approval.",
        secretary_id=sec.account_id,
        secretary_acted_at=_now(1),
        created_at=_now(6),
    ))
    db.flush()
    print("  [OK]   2 subject petitions seeded (1 PENDING, 1 SECRETARY_ENDORSED).")


def _seed_document_requests(db: Session, students: dict, sec: UserAccount) -> None:
    import random, string
    def ref(): return "REF-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    db.add(DocumentRequest(
        reference_number=ref(),
        requestor_account_id=students["maria.cruz@student.university.edu"].account_id,
        requestor_type="CURRENT_STUDENT",
        document_type="ENROLLMENT_CERT",
        purpose="Required for scholarship application at CHED Region VII.",
        status="PENDING",
        created_at=_now(3),
    ))
    db.add(DocumentRequest(
        reference_number=ref(),
        requestor_account_id=students["jose.mendoza@student.university.edu"].account_id,
        requestor_type="CURRENT_STUDENT",
        document_type="TRANSCRIPT",
        purpose="Needed for graduate school application at UP Diliman.",
        status="PROCESSING",
        secretary_notes="Verified enrollment records. Processing official transcript.",
        processed_by_secretary_id=sec.account_id,
        processing_started_at=_now(2),
        created_at=_now(5),
    ))
    db.add(DocumentRequest(
        reference_number=ref(),
        requestor_account_id=students["isabella.santos@student.university.edu"].account_id,
        requestor_type="CURRENT_STUDENT",
        document_type="GOOD_MORAL",
        purpose="Job application at Accenture Philippines.",
        status="READY_FOR_PICKUP",
        secretary_notes="Certificate signed and sealed. Ready for student pickup.",
        processed_by_secretary_id=sec.account_id,
        processing_started_at=_now(4),
        ready_at=_now(1),
        created_at=_now(6),
    ))
    db.flush()
    print("  [OK]   3 document requests seeded (PENDING, PROCESSING, READY_FOR_PICKUP).")


def _seed_orgs(db: Session, students: dict, sec: UserAccount) -> list[StudentOrganization]:
    orgs = []
    ccis_council = StudentOrganization(
        org_name="CCIS Student Council",
        org_acronym="CCIS-SC",
        org_type="ACADEMIC",
        description="Official student governing body of the College of Computing and Information Sciences.",
        submitted_by_account_id=students["jose.mendoza@student.university.edu"].account_id,
        status="RECOGNIZED",
        secretary_notes="Annual re-recognition granted. All requirements submitted.",
        processed_by=sec.account_id,
        processed_at=_now(90),
        created_at=_now(120),
    )
    nextech = StudentOrganization(
        org_name="NexTech Innovation Club",
        org_acronym="NTIC",
        org_type="ACADEMIC",
        description="Student-led organization focused on emerging technologies, hackathons, and tech entrepreneurship.",
        submitted_by_account_id=students["miguel.torres@student.university.edu"].account_id,
        status="PENDING",
        created_at=_now(5),
    )
    for org in [ccis_council, nextech]:
        db.add(org)
    db.flush()
    orgs = [ccis_council, nextech]
    print("  [OK]   2 student organizations seeded (1 RECOGNIZED, 1 PENDING).")
    return orgs


def _seed_bookings(db: Session, students: dict, sec: UserAccount, facilities: list, orgs: list) -> None:
    lab301 = facilities[0]
    sem101 = facilities[3]
    ccis_council = orgs[0]

    base_dt = _now(-7)  # booking date 7 days in the future
    book_date = base_dt.date()
    t_start = datetime(base_dt.year, base_dt.month, base_dt.day, 13, 0, 0, tzinfo=timezone.utc)
    t_end   = datetime(base_dt.year, base_dt.month, base_dt.day, 17, 0, 0, tzinfo=timezone.utc)

    db.add(FacilityBooking(
        facility_id=lab301.id,
        requestor_account_id=students["jose.mendoza@student.university.edu"].account_id,
        org_id=ccis_council.id,
        event_title="CCIS Hackathon 2025 — Preliminary Round",
        event_description="Annual hackathon organized by the CCIS Student Council. Teams will compete in web and mobile development.",
        booking_date=book_date,
        time_start=t_start, time_end=t_end,
        attendee_count=38,
        status="APPROVED",
        secretary_notes="Booking confirmed. Coordinate with IT support for network setup.",
        processed_by_secretary_id=sec.account_id,
        processed_at=_now(2),
        created_at=_now(5),
    ))

    base2_dt = _now(-3)
    book_date2 = base2_dt.date()
    t2_start = datetime(base2_dt.year, base2_dt.month, base2_dt.day, 9, 0, 0, tzinfo=timezone.utc)
    t2_end   = datetime(base2_dt.year, base2_dt.month, base2_dt.day, 12, 0, 0, tzinfo=timezone.utc)

    db.add(FacilityBooking(
        facility_id=sem101.id,
        requestor_account_id=students["maria.cruz@student.university.edu"].account_id,
        event_title="CS 304 Group Study & Review Session",
        event_description="Collaborative study session for Software Engineering 2 midterm coverage.",
        booking_date=book_date2,
        time_start=t2_start, time_end=t2_end,
        attendee_count=12,
        status="PENDING",
        created_at=_now(1),
    ))
    db.flush()
    print("  [OK]   2 facility bookings seeded (1 APPROVED, 1 PENDING).")


# ─────────────────────────────────────────────────────────────────────────────
# 10.  SUPPORT TICKETS
# ─────────────────────────────────────────────────────────────────────────────

def _seed_support(db: Session, students: dict) -> None:
    tickets = [
        SupportTicket(
            student_account_id=students["juan.santos@student.university.edu"].account_id,
            department="IT SUPPORT",
            issue_subject="Cannot submit enrollment form — page keeps loading",
            issue_description="I've been trying to submit my enrollment form for Year 1 Semester 1 for the past two days. The page loads indefinitely after I click submit. I've tried different browsers and cleared my cache but the issue persists. Please help.",
            ticket_status="OPEN",
        ),
        SupportTicket(
            student_account_id=students["carlos.reyes@student.university.edu"].account_id,
            department="ACADEMIC AFFAIRS",
            issue_subject="Midterm grade for CS 201 not appearing in my gradebook",
            issue_description="My professor said she already submitted the midterm grades for CS 201 (Algorithms and Complexity) last week, but it still shows blank in my student gradebook. My classmates already see their grades. Student number: 2023-00010.",
            ticket_status="OPEN",
        ),
        SupportTicket(
            student_account_id=students["ana.garcia@student.university.edu"].account_id,
            department="REGISTRAR",
            issue_subject="Request for Irregular Student Track Documentation",
            issue_description="I am an irregular student and need an official document certifying my current enrollment status and irregular track for the purpose of applying for a scholarship. Can the secretary assist with this?",
            ticket_status="OPEN",
        ),
    ]
    for t in tickets:
        db.add(t)
    db.flush()
    print("  [OK]   3 support tickets seeded.")


# ─────────────────────────────────────────────────────────────────────────────
# 11.  SYSTEM ANNOUNCEMENTS
# ─────────────────────────────────────────────────────────────────────────────

def _seed_announcements(db: Session) -> None:
    db.add(SystemAnnouncement(
        title="Enrollment for 2nd Semester A.Y. 2025–2026 is Now OPEN",
        body="The Office of the Registrar announces that enrollment for the 2nd Semester of Academic Year 2025–2026 is officially open. Students are advised to settle all financial obligations and secure clearances before proceeding with enrollment. Enrollment window closes on December 15, 2025.",
        type="announcement",
        status="ACTIVE",
    ))
    db.add(SystemAnnouncement(
        title="Scheduled System Maintenance — May 30, 2025 (12:00 AM–4:00 AM)",
        body="NexEnroll will undergo scheduled maintenance on May 30, 2025 from 12:00 AM to 4:00 AM (PHT). During this window, the enrollment portal and all services will be unavailable. Please complete any pending transactions before the maintenance window. We apologize for the inconvenience.",
        type="maintenance",
        status="ACTIVE",
    ))
    db.flush()
    print("  [OK]   2 system announcements seeded.")


# ─────────────────────────────────────────────────────────────────────────────
# 12.  WALL OF SHAME VIOLATORS
# ─────────────────────────────────────────────────────────────────────────────

OFFENSE_TYPES = [
    {"offense": "Explicit/Harassing content in support ticket",    "keywords": ["fuck", "shit"]},
    {"offense": "Threatening language toward faculty",             "keywords": ["kill", "harass"]},
    {"offense": "Hate speech and discriminatory remarks",          "keywords": ["idiot", "stupid"]},
    {"offense": "Sexual harassment via support channel",           "keywords": ["sex", "dick"]},
]

VIOLATOR_DATA = [
    ("Rico",    "Dela Cruz", "STUDENT", "rico.delacruz@student.university.edu",   3, [90, 75, 62], True,  "2021-00042", "BSCS"),
    ("Lara",   "Santos",    "STUDENT", "lara.santos@student.university.edu",      3, [30, 18, 10], True,  "2022-00087", "BSCS"),
    ("Marco",  "Reyes",     "STUDENT", "marco.reyes@student.university.edu",      4, [8,   5,  3,  1], True, "2023-00015", "BSCS"),
    ("Eduardo","Bautista",  "FACULTY", "e.bautista@faculty.university.edu",       3, [45, 32, 20], True,  None, None),
    ("Ana",    "Villanueva","STUDENT", "ana.villanueva@student.university.edu",    2, [14, 5],      False, "2023-00201", "BSCS"),
    ("Jose",   "Miranda",   "STUDENT", "jose.miranda@student.university.edu",     1, [3],          False, "2024-00033", "BSCS"),
]

def _seed_violators(db: Session) -> None:
    seeded = 0
    for first, last, role, email, strikes, days_list, is_banned, snum, course in VIOLATOR_DATA:
        if db.query(UserAccount).filter(UserAccount.email_address == email).first():
            continue
        violation_log = []
        for i, d in enumerate(days_list):
            tmpl = OFFENSE_TYPES[i % len(OFFENSE_TYPES)]
            violation_log.append({
                "offense": tmpl["offense"],
                "detected_at": _now(d).isoformat(),
                "keywords": tmpl["keywords"],
            })
        last_v = _now(min(days_list))
        u = UserAccount(
            email_address=email, hashed_password=PW,
            account_role=role, is_active_account=not is_banned,
            violation_count=strikes, last_violation_at=last_v,
            violation_log=violation_log,
        )
        db.add(u); db.flush()
        if role == "STUDENT" and snum:
            db.add(StudentProfile(
                student_account_id=u.account_id,
                first_name=first, last_name=last,
                student_number=snum, current_course=course,
                current_year_level=2, current_semester=1,
            ))
        elif role == "FACULTY":
            db.add(FacultyProfile(
                faculty_account_id=u.account_id,
                first_name=first, last_name=last,
                academic_department="CCIS", employee_id=f"FAC-BAN-{u.account_id:04d}",
                maximum_teaching_load=4, current_teaching_load=0,
                is_available_for_classes=False,
            ))
        db.flush()
        seeded += 1
    print(f"  [OK]   {seeded} Wall of Shame / Under Watch accounts seeded.")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────

def seed_database() -> None:
    Base.metadata.create_all(bind=database_engine)
    db = SessionLocal()
    try:
        print("\n-- NexEnroll Comprehensive Seed ------------------------------")

        _seed_settings(db)
        _seed_curriculum(db)
        admin = _ensure_admin(db)
        db.flush()

        _wipe(db, admin.account_id)

        sec      = _seed_secretary(db)
        faculty  = _seed_faculty(db)
        students = _seed_students(db)
        db.flush()

        _seed_enrollments(db, students)
        inc_gid = _seed_gradebook(db, students, faculty, admin)
        db.flush()

        facilities = _seed_facilities(db)
        _seed_equipment(db, students, faculty)
        _seed_ojt(db, students, sec)
        _seed_completion_request(db, students, sec, inc_gid)
        _seed_mapping_drafts(db, students, sec)
        _seed_petitions(db, students, sec)
        _seed_document_requests(db, students, sec)
        orgs = _seed_orgs(db, students, sec)
        _seed_bookings(db, students, sec, facilities, orgs)
        _seed_support(db, students)
        _seed_announcements(db)
        _seed_violators(db)

        db.commit()

        print("\n[OK]  Seed complete.")
        print("--------------------------------------------------------------")
        print("  ADMIN     : admin@university.edu                / admin123")
        print("  SECRETARY : secretary@university.edu            / student123")
        print("  FACULTY   : dr.santos@faculty.university.edu    / student123")
        print("  FACULTY   : prof.delacruz@faculty.university.edu/ student123")
        print("  FACULTY   : dr.reyes@faculty.university.edu     / student123")
        print("  FACULTY   : prof.torres@faculty.university.edu  / student123")
        print("  STUDENT   : juan.santos@student.university.edu  / student123  (Yr1 Sem1)")
        print("  STUDENT   : maria.cruz@student.university.edu   / student123  (Yr1 Sem2)")
        print("  STUDENT   : carlos.reyes@student.university.edu / student123  (Yr2 Sem1, transferee)")
        print("  STUDENT   : ana.garcia@student.university.edu   / student123  (Yr2 Sem2, irregular)")
        print("  STUDENT   : miguel.torres@student.university.edu/ student123  (Yr3 Sem1, OJT pending)")
        print("  STUDENT   : sophia.lim@student.university.edu   / student123  (Yr3 Sem2, INC on CS204)")
        print("  STUDENT   : jose.mendoza@student.university.edu / student123  (Yr4 Sem1, thesis)")
        print("  STUDENT   : isabella.santos@student.university.edu/student123 (Yr4 Sem2, graduating)")
        print("--------------------------------------------------------------\n")

    except Exception as err:
        print(f"\n[ERROR] {err}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
