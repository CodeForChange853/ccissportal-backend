from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.modules.enrollment.models import CurriculumSubject
from src.modules.faculty.models import GradebookEntry


# ── Status constants 

AVAILABLE          = "AVAILABLE"
BLOCKED            = "BLOCKED"
PENDING            = "PENDING"
ALREADY_COMPLETED  = "ALREADY_COMPLETED"
CURRENTLY_ENROLLED = "CURRENTLY_ENROLLED"

# Verdict constants (top-level recommendation)
VERDICT_APPROVE      = "APPROVE"
VERDICT_PARTIAL      = "PARTIAL"
VERDICT_CONDITIONAL  = "CONDITIONAL"
VERDICT_DEFER        = "DEFER"


# ── Data classes 

@dataclass
class SubjectCheckResult:
    subject_id:      int
    subject_code:    str
    subject_title:   str
    credit_units:    int
    status:          str
    prereq_code:     Optional[str]  = None
    prereq_title:    Optional[str]  = None
    prereq_status:   Optional[str]  = None   # how the student stands on the prereq
    blocking_reason: Optional[str]  = None


@dataclass
class RecommendationResult:
    verdict:          str
    pass_rate:        float
    available_count:  int
    blocked_count:    int
    pending_count:    int
    flagged_subjects: list[str]
    suggested_action: str
    subject_results:  list[SubjectCheckResult]


# ── Student academic snapshot ──────────────────────────────────────────────

@dataclass
class StudentSnapshot:

    passed_subject_ids:   set[int]
    failed_subject_ids:   set[int]
    enrolled_subject_ids: set[int]

    # Code → status for building human-readable prereq_status strings
    id_to_status: dict[int, str]


def _build_student_snapshot(
    db: Session,
    student_account_id: int,
) -> StudentSnapshot:
 
    entries = (
        db.query(GradebookEntry)
        .filter(
            GradebookEntry.student_account_id == student_account_id
        )
        .all()
    )

    passed   : set[int] = set()
    failed   : set[int] = set()
    enrolled : set[int] = set()
    id_to_status: dict[int, str] = {}

    for entry in entries:
        sid = entry.curriculum_subject_id
        id_to_status[sid] = entry.completion_status

        if entry.completion_status == "PASSED":
            passed.add(sid)
        elif entry.completion_status == "FAILED":
            failed.add(sid)
        elif entry.completion_status in ("IN PROGRESS", "INCOMPLETE"):
            enrolled.add(sid)

    return StudentSnapshot(
        passed_subject_ids=passed,
        failed_subject_ids=failed,
        enrolled_subject_ids=enrolled,
        id_to_status=id_to_status,
    )


# ── Core check function 

def _check_one_subject(
    subject: CurriculumSubject,
    snapshot: StudentSnapshot,
    prereq_subject: Optional[CurriculumSubject],
) -> SubjectCheckResult:

    sid = subject.subject_id

    # ── Already in history 
    if sid in snapshot.passed_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            status=ALREADY_COMPLETED,
            blocking_reason="Student already passed this subject.",
        )

    if sid in snapshot.enrolled_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            status=CURRENTLY_ENROLLED,
            blocking_reason="Student is currently enrolled in this subject.",
        )

    # ── No prerequisite → always available 
    if subject.prerequisite_subject_id is None:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            status=AVAILABLE,
        )

    # ── Has prerequisite — evaluate it 
    prereq_id    = subject.prerequisite_subject_id
    prereq_code  = prereq_subject.subject_code  if prereq_subject else str(prereq_id)
    prereq_title = prereq_subject.subject_title if prereq_subject else "Unknown"

    prereq_student_status = snapshot.id_to_status.get(prereq_id)

    if prereq_id in snapshot.passed_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            status=AVAILABLE,
            prereq_code=prereq_code,
            prereq_title=prereq_title,
            prereq_status="PASSED",
        )

    if prereq_id in snapshot.enrolled_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            status=PENDING,
            prereq_code=prereq_code,
            prereq_title=prereq_title,
            prereq_status="IN PROGRESS",
            blocking_reason=(
                f"Prerequisite '{prereq_code} — {prereq_title}' is currently "
                f"IN PROGRESS. Cannot confirm availability until it is graded."
            ),
        )

    if prereq_id in snapshot.failed_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            status=BLOCKED,
            prereq_code=prereq_code,
            prereq_title=prereq_title,
            prereq_status="FAILED",
            blocking_reason=(
                f"Prerequisite '{prereq_code} — {prereq_title}' was FAILED. "
                f"Student must retake and pass it first."
            ),
        )

    # Prereq was never taken at all
    return SubjectCheckResult(
        subject_id=sid,
        subject_code=subject.subject_code,
        subject_title=subject.subject_title,
        credit_units=subject.credit_units,
        status=BLOCKED,
        prereq_code=prereq_code,
        prereq_title=prereq_title,
        prereq_status="NOT TAKEN",
        blocking_reason=(
            f"Prerequisite '{prereq_code} — {prereq_title}' has not been "
            f"taken yet. It must be passed before this subject."
        ),
    )


# ── Verdict builder 

def _build_recommendation(
    subject_results: list[SubjectCheckResult],
    target_year: int,
    target_semester: int,
) -> RecommendationResult:

    enrollable = [
        r for r in subject_results
        if r.status not in (ALREADY_COMPLETED, CURRENTLY_ENROLLED)
    ]

    available = sum(1 for r in enrollable if r.status == AVAILABLE)
    blocked   = sum(1 for r in enrollable if r.status == BLOCKED)
    pending   = sum(1 for r in enrollable if r.status == PENDING)
    total     = len(enrollable)

    pass_rate     = available / total if total > 0 else 1.0
    flagged_codes = [
        r.subject_code for r in enrollable
        if r.status in (BLOCKED, PENDING)
    ]

    sem_label = {1: "1st", 2: "2nd", 3: "Summer"}.get(target_semester, str(target_semester))
    year_label = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(target_year, str(target_year))

    if blocked == 0 and pending == 0:
        verdict = VERDICT_APPROVE
        action  = (
            f"Student satisfies all prerequisites for "
            f"{year_label} Year {sem_label} Semester. Enrollment may proceed."
        )
    elif blocked == 0 and pending > 0:
        verdict = VERDICT_CONDITIONAL
        pend_list = ", ".join(flagged_codes)
        action  = (
            f"Pending prerequisites in progress: {pend_list}. "
            f"Approve conditionally — verify final grades before the next semester starts."
        )
    elif blocked > 0 and (blocked / total) < 0.5:
        verdict = VERDICT_PARTIAL
        block_list = ", ".join(r.subject_code for r in enrollable if r.status == BLOCKED)
        action  = (
            f"Remove blocked subjects before approving: {block_list}. "
            f"The remaining {available} subject(s) are clear."
        )
    else:
        verdict = VERDICT_DEFER
        action  = (
            f"Too many unmet prerequisites ({blocked}/{total} subjects blocked). "
            f"Student should retake failed subjects and re-enroll next semester."
        )

    return RecommendationResult(
        verdict=verdict,
        pass_rate=round(pass_rate, 4),
        available_count=available,
        blocked_count=blocked,
        pending_count=pending,
        flagged_subjects=flagged_codes,
        suggested_action=action,
        subject_results=subject_results,
    )


# ── Public API 

class PrerequisiteChecker:


    def __init__(self, db: Session) -> None:
        self._db = db

    def _load_prereq_subject(
        self, prereq_id: Optional[int]
    ) -> Optional[CurriculumSubject]:
        if prereq_id is None:
            return None
        return self._db.query(CurriculumSubject).filter(
            CurriculumSubject.subject_id == prereq_id
        ).first()

    # ── check_semester 

    def check_semester(
        self,
        student_account_id: int,
        year: int,
        semester: int,
    ) -> RecommendationResult:
 
        snapshot = _build_student_snapshot(self._db, student_account_id)

        subjects = (
            self._db.query(CurriculumSubject)
            .filter(
                CurriculumSubject.target_year_level == year,
                CurriculumSubject.target_semester   == semester,
            )
            .order_by(CurriculumSubject.subject_code)
            .all()
        )

        # Batch-load all prerequisite subjects in one query instead of one per subject
        prereq_ids = {
            s.prerequisite_subject_id
            for s in subjects
            if s.prerequisite_subject_id is not None
        }
        prereq_map: dict[int, CurriculumSubject] = {}
        if prereq_ids:
            prereqs = (
                self._db.query(CurriculumSubject)
                .filter(CurriculumSubject.subject_id.in_(prereq_ids))
                .all()
            )
            prereq_map = {p.subject_id: p for p in prereqs}

        results = [
            _check_one_subject(
                subject=s,
                snapshot=snapshot,
                prereq_subject=prereq_map.get(s.prerequisite_subject_id),
            )
            for s in subjects
        ]

        return _build_recommendation(results, year, semester)

    # ── check_subjects 

    def check_subjects(
        self,
        student_account_id: int,
        subject_codes: list[str],       
    ) -> RecommendationResult:

        if not subject_codes:
            return _build_recommendation([], 0, 0)

        snapshot = _build_student_snapshot(self._db, student_account_id)

        # Single bulk fetch for all requested subject codes
        subjects_found = (
            self._db.query(CurriculumSubject)
            .filter(CurriculumSubject.subject_code.in_(subject_codes))
            .all()
        )
        subject_map = {s.subject_code: s for s in subjects_found}

        # Collect all unique prerequisite IDs, then fetch them in one query
        prereq_ids = {
            s.prerequisite_subject_id
            for s in subjects_found
            if s.prerequisite_subject_id is not None
        }
        prereq_map: dict[int, CurriculumSubject] = {}
        if prereq_ids:
            prereqs = (
                self._db.query(CurriculumSubject)
                .filter(CurriculumSubject.subject_id.in_(prereq_ids))
                .all()
            )
            prereq_map = {p.subject_id: p for p in prereqs}

        results: list[SubjectCheckResult] = []
        year_levels: list[int] = []
        semesters:   list[int] = []

        for code in subject_codes:
            subject = subject_map.get(code)

            if subject is None:
                results.append(SubjectCheckResult(
                    subject_id=-1,
                    subject_code=code,
                    subject_title="Unknown Subject",
                    credit_units=0,
                    status=BLOCKED,
                    blocking_reason=(
                        f"Subject code '{code}' was not found in the curriculum database. "
                        f"Verify the subject code or update the curriculum."
                    ),
                ))
                continue

            prereq = prereq_map.get(subject.prerequisite_subject_id)
            results.append(_check_one_subject(subject, snapshot, prereq))
            year_levels.append(subject.target_year_level)
            semesters.append(subject.target_semester)

        target_year = max(year_levels) if year_levels else 0
        target_sem  = max(semesters)   if semesters   else 0

        return _build_recommendation(results, target_year, target_sem)

    # ── next_semester ──────────────────────────────────────────────────────

    def next_semester(
        self,
        student_account_id: int,
        current_year: int,
        current_semester: int,
    ) -> RecommendationResult:

        # Determine next year/semester
        if current_semester == 1:
            next_year, next_sem = current_year, 2
        elif current_semester == 2:
            # Check if a summer semester exists for this year
            summer_exists = self._db.query(CurriculumSubject).filter(
                CurriculumSubject.target_year_level == current_year,
                CurriculumSubject.target_semester   == 3,
            ).first() is not None

            if summer_exists:
                next_year, next_sem = current_year, 3
            else:
                next_year, next_sem = current_year + 1, 1
        elif current_semester == 3:
            next_year, next_sem = current_year + 1, 1
        else:
            # Unexpected semester value — default forward
            next_year, next_sem = current_year, current_semester + 1

        # Guard: 4th year 2nd semester is the last
        if current_year >= 4 and current_semester >= 2:
            return RecommendationResult(
                verdict=VERDICT_APPROVE,
                pass_rate=1.0,
                available_count=0,
                blocked_count=0,
                pending_count=0,
                flagged_subjects=[],
                suggested_action="Student has completed the final semester of the curriculum.",
                subject_results=[],
            )

        return self.check_semester(student_account_id, next_year, next_sem)

    # ── Academic standing snapshot (all three tabs at once) ────────────────

    def get_academic_standing(
        self,
        student_account_id: int,
        current_year: int,
        current_semester: int,
    ) -> dict:

        from src.modules.enrollment.models import CurriculumSubject as CS

        entries = (
            self._db.query(GradebookEntry, CS)
            .join(CS, GradebookEntry.curriculum_subject_id == CS.subject_id)
            .filter(GradebookEntry.student_account_id == student_account_id)
            .all()
        )

        current_subjects = []
        passed_subjects  = []

        for entry, subject in entries:
            record = {
                "subject_code":      subject.subject_code,
                "subject_title":     subject.subject_title,
                "credit_units":      subject.credit_units,
                "target_year_level": subject.target_year_level,
                "target_semester":   subject.target_semester,
                "midterm_grade":     entry.midterm_grade,
                "final_grade":       entry.final_grade,
                "completion_status": entry.completion_status,
            }

            if entry.completion_status == "IN PROGRESS":
                current_subjects.append(record)
            elif entry.completion_status == "PASSED":
                passed_subjects.append(record)

        # Sort passed subjects chronologically (year → semester → code)
        passed_subjects.sort(
            key=lambda r: (r["target_year_level"], r["target_semester"], r["subject_code"])
        )

        # Sort current subjects by code
        current_subjects.sort(key=lambda r: r["subject_code"])

        next_rec = self.next_semester(
            student_account_id, current_year, current_semester
        )

        return {
            "current_subjects":             current_subjects,
            "passed_subjects":              passed_subjects,
            "next_semester_recommendation": next_rec,
        }