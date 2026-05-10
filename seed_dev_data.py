import sys, os, random
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
 
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
from src.core.database_setup import SessionLocal
from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import (
    CurriculumSubject, StudentProfile, StudentEnrollmentRequest,
)
from src.modules.faculty.models import FacultyProfile, GradebookEntry
from src.modules.support.models import SupportTicket
from src.modules.audit.models import AuditEvent
 
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
 
# ── helpers 
 
def _get_or_create_user(db, email: str, role: str, password: str = "password123") -> UserAccount:
    existing = db.query(UserAccount).filter(UserAccount.email_address == email).first()
    if existing:
        return existing
    u = UserAccount(
        email_address=email,
        hashed_password=pwd.hash(password),
        account_role=role,
        is_active_account=True,
    )
    db.add(u)
    db.flush()
    return u
 
def _ago(days=0, hours=0, minutes=0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes)
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 1.  FACULTY  (5 members — loads: 4/4, 3/4, 2/4, 1/4, 0/4)
# ══════════════════════════════════════════════════════════════════════════════
 
FACULTY_DATA = [
    # (email,                    first,    last,       dept,               emp_id,     cur, max)
    ("santos.r@university.edu",  "Ramon",  "Santos",   "CS Department",    "FAC-101",  4,   4),  # AT CAP
    ("reyes.m@university.edu",   "Maria",  "Reyes",    "CS Department",    "FAC-102",  3,   4),  # HIGH
    ("cruz.j@university.edu",    "Jose",   "Cruz",     "IT Department",    "FAC-103",  2,   4),  # OK
    ("delacr.a@university.edu",  "Ana",    "Dela Cruz","IT Department",    "FAC-104",  1,   4),  # OK
    ("garcia.l@university.edu",  "Luis",   "Garcia",   "Mathematics Dept", "FAC-105",  0,   4),  # AVAILABLE
]
 
def seed_faculty(db) -> list[UserAccount]:
    accounts = []
    for email, first, last, dept, emp_id, cur_load, max_load in FACULTY_DATA:
        u = _get_or_create_user(db, email, "FACULTY")
        accounts.append(u)
 
        exists = db.query(FacultyProfile).filter(
            FacultyProfile.faculty_account_id == u.account_id
        ).first()
        if not exists:
            db.add(FacultyProfile(
                faculty_account_id=u.account_id,
                first_name=first,
                last_name=last,
                employee_id=emp_id,
                academic_department=dept,
                current_teaching_load=cur_load,
                maximum_teaching_load=max_load,
                is_available_for_classes=(cur_load < max_load),
            ))
            print(f"  [OK] Faculty: {first} {last}  load={cur_load}/{max_load}")
        else:
            print(f"  [SKIP] Faculty {email} already exists")
 
    db.flush()
    return accounts
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 2.  STUDENTS  (8 accounts across different years)
# ══════════════════════════════════════════════════════════════════════════════
 
STUDENT_DATA = [
    # (email,                     first,     last,        student_no,      course,  yr, sem)
    ("miguel.r@university.edu",   "Miguel",  "Ramos",     "2024-00002",    "BSCS",  1,  1),
    ("sofia.c@university.edu",    "Sofia",   "Castro",    "2024-00003",    "BSCS",  1,  2),
    ("carlo.m@university.edu",    "Carlo",   "Mendoza",   "2023-00010",    "BSIT",  2,  1),
    ("bianca.t@university.edu",   "Bianca",  "Torres",    "2023-00011",    "BSIT",  2,  2),
    ("kevin.l@university.edu",    "Kevin",   "Lim",       "2022-00020",    "BSCS",  3,  1),
    ("patricia.s@university.edu", "Patricia","Santos",    "2022-00021",    "BSIS",  3,  2),
    ("mark.a@university.edu",     "Mark",    "Aquino",    "2021-00030",    "BSCS",  4,  1),
    ("diana.v@university.edu",    "Diana",   "Villanueva","2021-00031",    "BSCS",  4,  2),
]
 
def seed_students(db) -> list[UserAccount]:
    accounts = []
    for email, first, last, snum, course, yr, sem in STUDENT_DATA:
        u = _get_or_create_user(db, email, "STUDENT")
        accounts.append(u)
 
        exists = db.query(StudentProfile).filter(
            StudentProfile.student_account_id == u.account_id
        ).first()
        if not exists:
            db.add(StudentProfile(
                student_account_id=u.account_id,
                first_name=first,
                last_name=last,
                student_number=snum,
                current_course=course,
                current_year_level=yr,
                current_semester=sem,
            ))
            print(f"  [OK] Student: {first} {last}  {course} Y{yr}S{sem}")
        else:
            print(f"  [SKIP] Student {email} already exists")
 
    db.flush()
    return accounts
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 3.  SUPPORT TICKETS  (30 tickets across 4 departments)
#     Feeds: SignalChart (confidence_score), ActivityGraph (category counts),
#            AlertFeed (status), RadarScanner (open IT/FINANCE blips)
# ══════════════════════════════════════════════════════════════════════════════
 
TICKET_TEMPLATES = [
    # (department,         status,     conf,  rerouted, subject,                          desc,                                             days_ago)
    # ── IT SUPPORT ──
    ("IT SUPPORT",        "OPEN",     0.93,  False, "Cannot access the student portal",
     "I have been unable to log into my student account for 3 days. Password reset email is not arriving.", 0),
 
    ("IT SUPPORT",        "OPEN",     0.88,  False, "LMS keeps crashing on upload",
     "Every time I try to submit a file on the Learning Management System, the page crashes.", 1),
 
    ("IT SUPPORT",        "OPEN",     0.41,  True,  "Wrong grade showing in portal",
     "My grade for CS 303 shows 5.0 but my professor confirmed it should be 1.75.",             1),  # low-conf, rerouted
 
    ("IT SUPPORT",        "PENDING",  0.85,  False, "Two-factor auth not working",
     "The OTP SMS is arriving but the system says it is invalid. Tried 5 times.",               2),
 
    ("IT SUPPORT",        "RESOLVED", 0.91,  False, "VPN access request",
     "I need VPN access to connect to the university library database for my thesis research.", 3),
 
    ("IT SUPPORT",        "RESOLVED", 0.87,  False, "Email quota exceeded",
     "My university email is returning an error that my quota is full.",                       4),
 
    ("IT SUPPORT",        "OPEN",     0.78,  False, "Slow internet in computer lab",
     "The computers in Room 302 have extremely slow internet, making online exams very difficult.", 0),
 
    ("IT SUPPORT",        "PENDING",  0.82,  False, "Cannot download transcript PDF",
     "The download button for the official transcript PDF produces a blank document.",         1),
 
    # ── REGISTRAR ──
    ("REGISTRAR",         "OPEN",     0.96,  False, "Enrollment form not submitted",
     "I completed the enrollment form but it says 'Pending' and never moved to 'Approved'.", 0),
 
    ("REGISTRAR",         "OPEN",     0.89,  False, "Name misspelling on official documents",
     "My surname is spelled 'Cruz' on my COR but 'Crux' on the official transcript.",         1),
 
    ("REGISTRAR",         "OPEN",     0.45,  True,  "Tuition balance dispute",
     "My tuition balance shows PHP 45,000 but I paid PHP 50,000 last month per my receipt.",  2),  # rerouted to FINANCE
 
    ("REGISTRAR",         "PENDING",  0.92,  False, "Request for certified true copy",
     "I need a certified true copy of my grades for a scholarship application.",               2),
 
    ("REGISTRAR",         "RESOLVED", 0.88,  False, "Late enrollment clearance",
     "I missed the enrollment deadline due to a medical emergency. Requesting clearance.",     5),
 
    ("REGISTRAR",         "RESOLVED", 0.94,  False, "Subject prerequisite waiver",
     "Requesting a waiver for ITE 3 prerequisite. I have equivalent knowledge from prior university.", 6),
 
    ("REGISTRAR",         "OPEN",     0.71,  False, "Missing grade in semester record",
     "CS 205 does not appear in my semester record even though I attended and passed.",        1),
 
    ("REGISTRAR",         "PENDING",  0.83,  False, "COR correction request",
     "My Certificate of Registration has the wrong section number listed for two subjects.", 3),
 
    # ── FINANCE ──
    ("FINANCE",           "OPEN",     0.97,  False, "Scholarship grant not credited",
     "My CHED scholarship grant for this semester has not been reflected in my balance.", 0),
 
    ("FINANCE",           "OPEN",     0.91,  False, "Installment plan request",
     "Due to financial hardship I am requesting to pay my tuition in three installments.",    1),
 
    ("FINANCE",           "OPEN",     0.86,  False, "Duplicate charge on billing statement",
     "I was charged twice for the miscellaneous fee. Both entries appear on my billing statement.", 0),
 
    ("FINANCE",           "PENDING",  0.79,  False, "Refund for dropped subject",
     "I officially dropped CS Elec 3 within the refund period but have not received the refund.", 3),
 
    ("FINANCE",           "RESOLVED", 0.93,  False, "Payment receipt not recorded",
     "I paid at the cashier on March 14 but the portal still shows an unpaid balance.",       7),
 
    ("FINANCE",           "RESOLVED", 0.88,  False, "Wrong amount in billing statement",
     "My billing statement shows PHP 2,500 for laboratory fees but the actual rate is PHP 1,500.", 8),
 
    ("FINANCE",           "PENDING",  0.72,  False, "Late payment penalty waiver",
     "I was charged a late payment penalty due to a bank processing delay. Requesting waiver.", 4),
 
    # ── ACADEMIC AFFAIRS ──
    ("ACADEMIC AFFAIRS",  "OPEN",     0.94,  False, "Incomplete grade removal request",
     "I completed my missing requirements for CS 306 two weeks ago but the INC is still on record.", 0),
 
    ("ACADEMIC AFFAIRS",  "OPEN",     0.87,  False, "Academic load overload request",
     "I am requesting permission to take 7 subjects this semester to graduate on time.",      1),
 
    ("ACADEMIC AFFAIRS",  "OPEN",     0.76,  False, "Cross-enrollment to another university",
     "Requesting approval to cross-enroll in one elective at Ateneo de Manila.",              2),
 
    ("ACADEMIC AFFAIRS",  "PENDING",  0.90,  False, "Thesis adviser assignment",
     "I have been waiting for a thesis adviser assignment for 3 weeks. Thesis 1 starts next month.", 3),
 
    ("ACADEMIC AFFAIRS",  "RESOLVED", 0.85,  False, "Petition for late withdrawal",
     "Requesting late withdrawal from CS 407 due to a conflict with my OJT schedule.",       9),
 
    ("ACADEMIC AFFAIRS",  "RESOLVED", 0.92,  False, "Honors eligibility verification",
     "Requesting verification that my GWA qualifies me for Cum Laude graduation honors.",    10),
 
    ("ACADEMIC AFFAIRS",  "PENDING",  0.68,  False, "Subject equivalency evaluation",
     "Requesting evaluation of two subjects taken at a previous university for equivalency credit.", 5),
]
 
def seed_tickets(db, student_accounts: list[UserAccount], admin_account: UserAccount) -> None:
    existing_count = db.query(SupportTicket).count()
    if existing_count >= 30:
        print(f"  [SKIP] Tickets already seeded ({existing_count} found)")
        return
 
    students = student_accounts[:]
    random.seed(42)
 
    inserted = 0
    for (dept, status, conf, rerouted, subject, desc, days_ago) in TICKET_TEMPLATES:
        # Rotate through students so tickets are distributed
        student = students[inserted % len(students)]
 
        # Spread timestamps: vary by hours within the day
        hour_offset = random.randint(0, 22)
        created = _ago(days=days_ago, hours=hour_offset)
 
        ticket = SupportTicket(
            student_account_id=student.account_id,
            issue_subject=subject,
            issue_description=desc,
            ai_predicted_category=dept,
            confidence_score=conf,
            was_manually_rerouted=rerouted,
            ticket_status=status,
        )
        # Manually set created_at via direct attribute (bypass server_default)
        ticket.created_at = created
        db.add(ticket)
        inserted += 1
 
    db.flush()
    print(f"  [OK] {inserted} support tickets seeded across 4 departments")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 4.  AUDIT EVENTS  (60 events — feeds AnomalyGauge + AuditTable)
#     IsolationForest needs ≥5 events; 60 gives it enough variance to
#     produce a meaningful anomaly score.
# ══════════════════════════════════════════════════════════════════════════════
 
# Event types and their realistic data
AUDIT_EVENTS = [
    # ── Normal login activity (20 events, score 0)
    *[("LOGIN_SUCCESS",       "student",  0.0,  f"student{i}@university.edu", "student",  None,  None,  i * 2)     for i in range(8)],
    *[("LOGIN_SUCCESS",       "faculty",  0.0,  f"faculty{i}@university.edu", "faculty",  None,  None,  i * 3 + 1)  for i in range(7)],
    *[("LOGIN_SUCCESS",       "admin",    0.0,  "admin@university.edu",       "admin",    None,  None,  i * 4)      for i in range(5)],
 
    # ── Enrollment actions (12 events)
    *[("ENROLLMENT_APPROVED", None, 0.0,  "admin@university.edu", "student", str(i), None,  i + 1) for i in range(1, 5)],
    *[("ENROLLMENT_REJECTED", None, 35.0, "admin@university.edu", "student", str(i), None,  i + 2) for i in range(5, 8)],
    *[("DOCUMENT_SCANNED",    None, 35.0, "admin@university.edu", "document", str(i), None, i)     for i in range(1, 5)],
    ("STUDENT_ADMITTED", None, 0.0, "admin@university.edu", "student", "99", None, 0),
 
    # ── Grade actions (6 events — sensitive)
    ("GRADE_MODIFIED", None, 35.0, "santos.r@university.edu",  "student", "2", None, 1),
    ("GRADE_MODIFIED", None, 35.0, "reyes.m@university.edu",   "student", "3", None, 2),
    # Off-hours grade modification — HIGH RISK (score 75)
    ("GRADE_MODIFIED", None, 75.0, "cruz.j@university.edu",    "student", "4",
     {"note": "Modified at 02:15 UTC", "threat_mitigation_engaged": False}, 0),
    ("GRADE_MODIFIED", None, 75.0, "unknown@external.com",     "student", "5",
     {"note": "Unrecognised actor off-hours"}, 0),
 
    # ── System / security events
    ("SETTING_CHANGED",  None, 35.0, "admin@university.edu", "setting", "1", None, 5),
    ("PASSKEY_ROTATED",  None, 75.0, "admin@university.edu", "setting", "1",
     {"note": "Passkey rotated at 03:10 UTC — flagged"}, 0),
    ("USER_SUSPENDED",   None, 75.0, "admin@university.edu", "user", "7",
     {"target_email": "problem.user@university.edu", "reason": "AI tripwire"}, 1),
    ("USER_SUSPENDED",   None, 75.0, "admin@university.edu", "user", "8",
     {"target_email": "flagged2@university.edu", "reason": "Off-hours login"}, 0),
    ("USER_ACTIVATED",   None, 0.0,  "admin@university.edu", "user", "9", None, 3),
 
    # ── Faculty & ticket events
    *[("FACULTY_ASSIGNED", None, 0.0, "admin@university.edu", "faculty", str(i), None, i) for i in range(1, 7)],
    *[("TICKET_RESOLVED",  None, 0.0, "admin@university.edu", "ticket",  str(i), None, i) for i in range(1, 6)],
]
 
def seed_audit_events(db, admin_account: UserAccount) -> None:
    existing_count = db.query(AuditEvent).count()
    if existing_count >= 50:
        print(f"  [SKIP] Audit events already seeded ({existing_count} found)")
        return
 
    random.seed(7)
    inserted = 0
    for row in AUDIT_EVENTS:
        (event_type, target_type, anomaly_score, actor_email,
         tgt_type, target_id, payload, days_ago) = row
 
        # Spread events realistically — vary hour to simulate off-hours activity
        hour = 2 if anomaly_score >= 75 else random.randint(8, 20)
        minutes = random.randint(0, 59)
        ts = _ago(days=days_ago, hours=hour, minutes=minutes)
        # Ensure timezone-aware
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
 
        event = AuditEvent(
            actor_id=admin_account.account_id if "admin" in actor_email else None,
            actor_email=actor_email,
            event_type=event_type,
            target_type=tgt_type or target_type,
            target_id=target_id,
            ip_address=f"192.168.1.{random.randint(1, 254)}",
            payload=payload,
            anomaly_score=anomaly_score,
        )
        event.created_at = ts
        db.add(event)
        inserted += 1
 
    db.flush()
    print(f"  [OK] {inserted} audit events seeded (includes HIGH-RISK off-hours events)")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 5.  ENROLLMENT REQUESTS  (12 — feeds RadarScanner + ReviewEnrollments page)
# ══════════════════════════════════════════════════════════════════════════════
 
ENROLL_REQUESTS = [
    # (year_level, semester, review_status, admin_notes,          days_ago)
    (1, 1, "PENDING",  None,                                   0),   # brand new
    (1, 1, "PENDING",  None,                                   1),
    (2, 1, "PENDING",  None,                                   2),
    (2, 2, "PENDING",  None,                                   3),
    (3, 1, "PENDING",  None,                                   5),   # 5 days old — amber age indicator
    (1, 2, "APPROVED", "All prerequisites met.",               4),
    (2, 1, "APPROVED", "COR verified — approved.",             6),
    (2, 2, "APPROVED", "Approved after document review.",      8),
    (3, 2, "APPROVED", "Senior student — fast-tracked.",       10),
    (1, 1, "REJECTED", "Incomplete COR documentation.",        3),
    (2, 1, "REJECTED", "Failed prerequisite: ITE 3.",          7),
    (3, 1, "REJECTED", "Student already enrolled this sem.",   9),
]
 
def seed_enrollment_requests(db, student_accounts: list[UserAccount]) -> None:
    existing_count = db.query(StudentEnrollmentRequest).count()
    if existing_count >= 12:
        print(f"  [SKIP] Enrollment requests already seeded ({existing_count} found)")
        return
 
    random.seed(13)
    inserted = 0
    for i, (yr, sem, status, notes, days_ago) in enumerate(ENROLL_REQUESTS):
        student = student_accounts[i % len(student_accounts)]
        # Avoid duplicate (same student + same year/sem)
        duplicate = db.query(StudentEnrollmentRequest).filter(
            StudentEnrollmentRequest.student_account_id == student.account_id,
            StudentEnrollmentRequest.target_year_level  == yr,
            StudentEnrollmentRequest.target_semester    == sem,
        ).first()
        if duplicate:
            continue
 
        hour = random.randint(8, 18)
        ts = _ago(days=days_ago, hours=hour)
 
        req = StudentEnrollmentRequest(
            student_account_id=student.account_id,
            target_year_level=yr,
            target_semester=sem,
            review_status=status,
            admin_review_notes=notes,
            extracted_subjects=[],
            verification_result=[],
            ai_recommendation={"verdict": "APPROVE" if status == "APPROVED" else "REVIEW"},
        )
        req.date_submitted = ts
        db.add(req)
        inserted += 1
 
    db.flush()
    print(f"  [OK] {inserted} enrollment requests seeded (5 PENDING / 4 APPROVED / 3 REJECTED)")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# 6.  GRADEBOOK ENTRIES  (for students — feeds AdminGrading + Faculty views)
# ══════════════════════════════════════════════════════════════════════════════
 
# Year-1 Sem-1 codes — everyone gets a few passed subjects
Y1S1_CODES = ["ITE 1", "ITE 2", "CS 101", "GE 1", "GE 2"]
Y1S2_CODES = ["GE 3", "ITE 3", "ITE 4", "CS 102", "GE 4"]
Y2S1_CODES = ["CS 201", "CS 202", "ITE 5", "GE 5"]
 
# (student index, subject codes, status, midterm, final)
EXTRA_GRADES = [
    # Miguel (index 0) — 1st year, just starting
    (0, Y1S1_CODES[:3], "IN PROGRESS", 2.00, None),
 
    # Sofia (index 1) — finished 1st sem, in 2nd
    (1, Y1S1_CODES,      "PASSED",     1.75, 1.75),
    (1, Y1S2_CODES[:3],  "IN PROGRESS", 2.25, None),
 
    # Carlo (index 2) — 2nd year 1st sem
    (2, Y1S1_CODES,      "PASSED",     1.50, 1.50),
    (2, Y1S2_CODES,      "PASSED",     1.75, 1.75),
    (2, Y2S1_CODES[:2],  "IN PROGRESS", 2.00, None),
 
    # Bianca (index 3) — 2nd year 2nd sem
    (3, Y1S1_CODES,      "PASSED",     2.00, 2.00),
    (3, Y1S2_CODES,      "PASSED",     2.25, 2.25),
    (3, Y2S1_CODES,      "PASSED",     2.00, 2.00),
    (3, ["ITE 6", "CS 203"], "IN PROGRESS", 1.75, None),
 
    # Kevin (index 4) — 3rd year 1st sem
    (4, Y1S1_CODES,      "PASSED",     1.25, 1.25),
    (4, Y1S2_CODES,      "PASSED",     1.50, 1.50),
    (4, Y2S1_CODES,      "PASSED",     1.75, 1.75),
    (4, ["CS 301", "CS 302", "CS 303"], "IN PROGRESS", 2.00, None),
]
 
def seed_gradebook(db, student_accounts: list[UserAccount], faculty_accounts: list[UserAccount]) -> None:
    # Get subject code → id mapping
    code_to_id: dict[str, int] = {
        s.subject_code: s.subject_id
        for s in db.query(CurriculumSubject).all()
    }
 
    inserted = 0
    for (student_idx, codes, status, midterm, final_grade) in EXTRA_GRADES:
        if student_idx >= len(student_accounts):
            continue
        student = student_accounts[student_idx]
 
        for code in codes:
            sid = code_to_id.get(code)
            if sid is None:
                continue
 
            # Skip if already exists
            exists = db.query(GradebookEntry).filter(
                GradebookEntry.student_account_id    == student.account_id,
                GradebookEntry.curriculum_subject_id == sid,
            ).first()
            if exists:
                continue
 
            db.add(GradebookEntry(
                student_account_id=student.account_id,
                faculty_account_id=faculty_accounts[0].account_id,
                curriculum_subject_id=sid,
                midterm_grade=midterm,
                final_grade=final_grade,
                completion_status=status,
            ))
            inserted += 1
 
    db.flush()
    if inserted:
        print(f"  [OK] {inserted} gradebook entries seeded")
    else:
        print("  [SKIP] Gradebook entries already exist")
 
 
# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
 
def main():
    print("\n" + "=" * 62)
    print("  NexEnroll Dev Data Seeder - lighting up all frontend graphs")
    print("=" * 62)
 
    db = SessionLocal()
    try:
        # Get the admin account (must already exist from seed_database.py)
        admin = db.query(UserAccount).filter(
            UserAccount.email_address == "admin@university.edu"
        ).first()
        if admin is None:
            print("\n[ERROR]  Admin account not found.")
            print("    Run seed_database.py first, then re-run this script.\n")
            return
 
        print("\n[1/6] Seeding faculty members...")
        faculty_accounts = seed_faculty(db)
 
        print("\n[2/6] Seeding student accounts...")
        student_accounts = seed_students(db)
 
        print("\n[3/6] Seeding support tickets...")
        seed_tickets(db, student_accounts, admin)
 
        print("\n[4/6] Seeding audit events...")
        seed_audit_events(db, admin)
 
        print("\n[5/6] Seeding enrollment requests...")
        seed_enrollment_requests(db, student_accounts)
 
        print("\n[6/6] Seeding gradebook entries...")
        seed_gradebook(db, student_accounts, faculty_accounts)
 
        db.commit()
 
        print("\n" + "=" * 62)
        print("  [SUCCESS]  Dev data seeded successfully!")
        print("=" * 62)
        print("""
WHAT TO EXPECT IN THE FRONTEND
---------------------------------------------------------------
  AdminOverview KPI strip:
    * Total Students: 9+ (original test student + 8 new)
    * Total Faculty:  5  (loads: 4/4 - 3/4 - 2/4 - 1/4 - 0/4)
    * Pending Enrollments: 5
 
  RadarScanner:
    * 5 cyan blips   -> PENDING enrollment requests
    * 4 red/orange blips -> OPEN IT SUPPORT + FINANCE tickets
 
  AlertFeed:
    * OPEN tickets from all 4 departments - live severity feed
 
  SignalChart (Neural Confidence Trend):
    * 30-point line - values range 41 % -> 97 %
    * NOTE: requires the AdminTicketResponse schema fix below!
 
  ActivityGraph (Triage Activity Map):
    * IT SUPPORT:       8 tickets   (cyan)
    * REGISTRAR:        8 tickets   (purple)
    * FINANCE:          7 tickets   (orange)
    * ACADEMIC AFFAIRS: 7 tickets   (green)
 
  Faculty Load Status sidebar:
    * Santos - FULL  (4/4)
    * Reyes  - HIGH  (3/4)
    * Cruz   - OK    (2/4)
    * Others - OK / AVAILABLE
 
  AuditIntelligence (AnomalyGauge):
    * 60 events including 6 HIGH-RISK (score 75) off-hours entries
    * IsolationForest fires -> gauge shows elevated score
    * Top anomalies section populated with GRADE_MODIFIED +
      PASSKEY_ROTATED + USER_SUSPENDED entries
 
---------------------------------------------------------------
REQUIRED BACKEND FIX - SignalChart will be empty without this:
 
  File: backend-v2/src/modules/support/schemas.py
  Reason: AdminTicketResponse is missing confidence_score and
          was_manually_rerouted — both read by the frontend.
 
  Find:
    class AdminTicketResponse(BaseModel):
        ticket_id: int
        student_account_id: int
        issue_subject: str
        issue_description: str
        ai_predicted_category: str
        ticket_status: str
        created_at: Optional[datetime] = None
 
  Replace with:
    class AdminTicketResponse(BaseModel):
        ticket_id: int
        student_account_id: int
        issue_subject: str
        issue_description: str
        ai_predicted_category: str
        confidence_score: Optional[float] = None
        was_manually_rerouted: bool = False
        ticket_status: str
        created_at: Optional[datetime] = None
---------------------------------------------------------------
""")
    except Exception as err:
        print(f"\n[ERROR]  Seeding error: {err}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()
 
 
if __name__ == "__main__":
    main()