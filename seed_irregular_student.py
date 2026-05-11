"""
seed_irregular_student.py
─────────────────────────
Creates ONE demo student account with a realistic academic history:
  - Year 1 Sem 1 → PASSED (all subjects, clean record)
  - Year 1 Sem 2 → PASSED  except GE 2  (FAILED — minor back subject)
  - Year 2 Sem 1 → PASSED  except CS 201 (FAILED — major, at 3.0 retention grade)
  - Year 2 Sem 2 → PASSED  except CS 203 (FAILED — major, 3.0 retention grade)
  - Year 3 Sem 1 → PASSED  except CS 301 (FAILED — major, 3.0 → triggers UNDER RETENTION)
  - Year 3 Sem 2 → Currently ENROLLED (present semester)

This account will:
  ✓ Show IRREGULAR badge in SmartEnrollmentTab
  ✓ Show UNDER RETENTION banner (3 major subjects at 3.0)
  ✓ Show Back Subjects pool with GE 2, CS 201, CS 203, CS 301
  ✓ AI Scheduler recommends Year 4 Sem 1 subjects
  ✓ CS 301 blocks any subject that requires it (e.g., CS 401 if defined)
  ✓ Demonstrates "Add All" back subject prompt

Login credentials:
  Email:    irregular.demo@university.edu
  Password: Demo@1234
"""

import sys, os
from passlib.context import CryptContext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.database_setup import SessionLocal
from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import CurriculumSubject, StudentProfile
from src.modules.faculty.models import FacultyProfile, GradebookEntry

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
DEMO_EMAIL    = "irregular.demo@university.edu"
DEMO_PASSWORD = "Demo@1234"
DEMO_COURSE   = "BSCS"

# Academic history definition
# (year, semester, subject_codes, completion_status, midterm, final_grade)
# For FAILED subjects: midterm has a value, final_grade = 3.0 (for MAJOR) or 5.0 (for MINOR)
HISTORY = [
    # ── Year 1 Sem 1: All PASSED cleanly
    (1, 1, [
        ("CS 101",  "PASSED",      1.75, 1.75),
        ("ITE 1",   "PASSED",      1.75, 1.75),
        ("ITE 2",   "PASSED",      2.00, 2.00),
        ("GE 1",    "PASSED",      1.50, 1.50),
        ("GE 2",    "PASSED",      2.00, 2.00),
        ("NSTP 1",  "PASSED",      1.00, 1.00),
    ]),

    # ── Year 1 Sem 2: GE 3 FAILED (minor back subject)
    (1, 2, [
        ("CS 102",  "PASSED",      2.00, 2.00),
        ("ITE 3",   "PASSED",      1.75, 1.75),
        ("ITE 4",   "PASSED",      2.25, 2.25),
        ("GE 3",    "FAILED",      3.00, 5.00),   # MINOR — back subject (no prereq)
        ("GE 4",    "PASSED",      2.00, 2.00),
        ("NSTP 2",  "PASSED",      1.00, 1.00),
    ]),

    # ── Year 2 Sem 1: CS 201 FAILED at 3.0 (MAJOR — 1st retention strike)
    (2, 1, [
        ("CS 201",  "FAILED",      3.00, 3.00),   # MAJOR w/ prereq → 1st retention strike
        ("CS 202",  "PASSED",      2.25, 2.25),
        ("ITE 5",   "PASSED",      1.75, 1.75),
        ("GE 5",    "PASSED",      2.00, 2.00),
        ("GE ELEC 1", "PASSED",    2.00, 2.00),
    ]),

    # ── Year 2 Sem 2: CS 203 FAILED at 3.0 (MAJOR — 2nd retention strike)
    (2, 2, [
        ("CS 203",  "FAILED",      3.00, 3.00),   # MAJOR w/ prereq → 2nd retention strike
        ("ITE 6",   "PASSED",      2.00, 2.00),
        ("CS 204",  "PASSED",      2.25, 2.25),
        ("GE 6",    "PASSED",      1.75, 1.75),
        ("GE ELEC 2", "PASSED",    2.00, 2.00),
    ]),

    # ── Year 3 Sem 1: CS 301 FAILED at 3.0 (MAJOR — 3rd retention strike → UNDER RETENTION!)
    (3, 1, [
        ("CS 301",  "FAILED",      3.00, 3.00),   # MAJOR w/ prereq → triggers UNDER_RETENTION
        ("CS 302",  "PASSED",      2.25, 2.25),
        ("CS 303",  "PASSED",      2.00, 2.00),
        ("ITE 7",   "PASSED",      1.75, 1.75),
        ("GE ELEC 3", "PASSED",    2.00, 2.00),
    ]),

    # ── Year 3 Sem 2: CURRENTLY ENROLLED (present semester)
    (3, 2, [
        ("CS 304",  "ENROLLED",    None, None),
        ("CS 305",  "ENROLLED",    None, None),
        ("ITE 8",   "ENROLLED",    None, None),
        ("GE ELEC 4", "ENROLLED",  None, None),
    ]),
]


def main():
    print()
    print("=" * 60)
    print("  Irregular Student Demo Seeder")
    print("=" * 60)

    db = SessionLocal()
    try:
        # ── 1. Get or create the student user account ─────────────────────
        existing_user = db.query(UserAccount).filter(
            UserAccount.email_address == DEMO_EMAIL
        ).first()

        if existing_user:
            print(f"\n[INFO] Account already exists — wiping gradebook and profile for clean reseed.")
            # Wipe existing gradebook entries for this student
            db.query(GradebookEntry).filter(
                GradebookEntry.student_account_id == existing_user.account_id
            ).delete()
            # Wipe existing profile
            db.query(StudentProfile).filter(
                StudentProfile.student_account_id == existing_user.account_id
            ).delete()
            db.flush()
            student = existing_user
        else:
            student = UserAccount(
                email_address=DEMO_EMAIL,
                hashed_password=pwd.hash(DEMO_PASSWORD),
                account_role="STUDENT",
                is_active_account=True,
            )
            db.add(student)
            db.flush()
            print(f"\n[OK] Created student account: {DEMO_EMAIL}")

        # ── 2. Create student profile (current: Year 3 Sem 2) ─────────────
        profile = StudentProfile(
            student_account_id=student.account_id,
            first_name="Juan",
            last_name="dela Cruz",
            student_number="2022-IRREG-001",
            current_course=DEMO_COURSE,
            current_year_level=3,
            current_semester=2,
        )
        db.add(profile)
        db.flush()
        print("[OK] Student profile created — Year 3, Sem 2, BSCS")

        # ── 3. Get all curriculum subjects by code ────────────────────────
        all_subjects: dict[str, CurriculumSubject] = {
            s.subject_code: s
            for s in db.query(CurriculumSubject).all()
        }
        print(f"[INFO] {len(all_subjects)} curriculum subjects found in DB")

        # ── 4. Get fallback faculty ───────────────────────────────────────
        faculty = db.query(FacultyProfile).first()
        if faculty is None:
            print("[ERROR] No faculty profiles found in DB.")
            print("        Run seed_dev_data.py first to create faculty accounts.")
            return
        fac_id = faculty.faculty_account_id
        print(f"[INFO] Using faculty ID {fac_id} for all gradebook entries")

        # ── 5. Seed gradebook entries ─────────────────────────────────────
        inserted  = 0
        skipped   = 0
        not_found = []

        for (year, semester, subjects) in HISTORY:
            print(f"\n  >> Seeding Year {year} Sem {semester}...")
            for (code, status, midterm, final_grade) in subjects:
                subj = all_subjects.get(code)
                if subj is None:
                    not_found.append(code)
                    print(f"      [SKIP] '{code}' not in curriculum — skipping")
                    continue

                # Use assigned faculty if there's a template row
                assigned = db.query(GradebookEntry).filter(
                    GradebookEntry.curriculum_subject_id == subj.subject_id,
                    GradebookEntry.student_account_id    == None,
                ).first()
                real_fac_id = assigned.faculty_account_id if assigned else fac_id

                entry = GradebookEntry(
                    student_account_id=student.account_id,
                    faculty_account_id=real_fac_id,
                    curriculum_subject_id=subj.subject_id,
                    midterm_grade=midterm,
                    system_grade=final_grade,
                    final_grade=final_grade,
                    completion_status=status,
                )
                db.add(entry)
                inserted += 1

                status_label = {
                    "PASSED":   "[PASS]",
                    "FAILED":   "[FAIL]",
                    "ENROLLED": "[ENROLLED]",
                }.get(status, f"[{status}]")
                grade_str = f"{final_grade}" if final_grade is not None else "—"
                print(f"      {status_label} {code:15s}  final={grade_str}")

        db.commit()

        # ── 6. Summary ────────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("  [SUCCESS] Irregular student demo account seeded!")
        print("=" * 60)
        print(f"""
  LOGIN CREDENTIALS
  --------------------------------------------
  Email:     {DEMO_EMAIL}
  Password:  {DEMO_PASSWORD}
  --------------------------------------------

  WHAT YOU SHOULD SEE IN THE STUDENT DASHBOARD
  --------------------------------------------
  Status Bar:  IRREGULAR STUDENT badge (orange)

  Retention:   UNDER RETENTION warning (red)
               3 major subjects scored 3.0:
               [MAJOR] CS 201 (Year 2 Sem 1)
               [MAJOR] CS 203 (Year 2 Sem 2)
               [MAJOR] CS 301 (Year 3 Sem 1)

  Back Subjects Pool (orange drag zone):
               MAJOR  - CS 201  (blocks CS 202-chain)
               MAJOR  - CS 203  (blocks CS 204-chain)
               MAJOR  - CS 301  (blocks CS 302-chain)
               MINOR  - GE 3    (no blocking, extra load)

  AI Prompt:   "You have 4 back subjects to retake.
               Do you want to add them before enrolling?"

  Next Semester Recommendation: Year 4 Sem 1
               Subjects without CS 301 prereq - AVAILABLE
               Subjects requiring CS 301      - BLOCKED
""")

        if not_found:
            print(f"  [NOTE] These subject codes were not in the curriculum DB")
            print(f"         and were skipped: {', '.join(not_found)}")
            print(f"         Add them via the Admin > Curriculum panel if needed.")
        print()

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
