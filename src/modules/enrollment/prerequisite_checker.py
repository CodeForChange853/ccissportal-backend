from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from src.modules.enrollment.models import CurriculumSubject
from src.modules.faculty.models import GradebookEntry


# ── Status constants ──────────────────────────────────────────────────────────

AVAILABLE          = "AVAILABLE"
BLOCKED            = "BLOCKED"
PENDING            = "PENDING"
ALREADY_COMPLETED  = "ALREADY_COMPLETED"
CURRENTLY_ENROLLED = "CURRENTLY_ENROLLED"
BACK_SUBJECT       = "BACK_SUBJECT"   # failed subject recommended for retake

# Verdict constants (top-level recommendation)
VERDICT_APPROVE      = "APPROVE"
VERDICT_PARTIAL      = "PARTIAL"
VERDICT_CONDITIONAL  = "CONDITIONAL"
VERDICT_DEFER        = "DEFER"

# Subject type constants
SUBJECT_MAJOR   = "MAJOR"
SUBJECT_MINOR   = "MINOR"
SUBJECT_SPECIAL = "SPECIAL"   # NSTP, LTS, CWTS, ROTC, PATHFIT

# Retention status constants
RETENTION_GOOD    = "GOOD"
RETENTION_AT_RISK = "AT_RISK"
RETENTION_UNDER   = "UNDER_RETENTION"
RETENTION_DROPOUT = "DROPOUT_RISK"

# Special subject code keywords
SPECIAL_KEYWORDS = ("NSTP", "LTS", "CWTS", "ROTC", "PATHFIT")


# ── Subject type classifier ───────────────────────────────────────────────────

def classify_subject(subject: CurriculumSubject) -> str:
    """
    Classify a subject:
    - SPECIAL  → code contains NSTP, LTS, CWTS, ROTC, PATHFIT (weekend programs)
    - MAJOR    → has a prerequisite_subject_id (is part of an advanced chain)
    - MINOR/GE → no prerequisite and not special
    """
    code_upper = (subject.subject_code or "").upper()
    if any(kw in code_upper for kw in SPECIAL_KEYWORDS):
        return SUBJECT_SPECIAL
    if subject.prerequisite_subject_id is not None:
        return SUBJECT_MAJOR
    return SUBJECT_MINOR


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SubjectCheckResult:
    subject_id:      int
    subject_code:    str
    subject_title:   str
    credit_units:    int
    status:          str
    subject_type:    str             = SUBJECT_MINOR
    prereq_code:     Optional[str]  = None
    prereq_title:    Optional[str]  = None
    prereq_status:   Optional[str]  = None
    blocking_reason: Optional[str]  = None
    priority_score:  Optional[int]  = None   # SE-05: ranking score for AVAILABLE subjects


@dataclass
class BackSubjectRecord:
    subject_id:      int
    subject_code:    str
    subject_title:   str
    credit_units:    int
    subject_type:    str
    times_failed:    int
    blocking_reason: Optional[str]  = None


@dataclass
class RetentionStatus:
    status:                str
    message:               str
    at_risk_major_count:   int  = 0
    failed_units:          int  = 0


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


# ── Student academic snapshot ─────────────────────────────────────────────────

@dataclass
class StudentSnapshot:
    passed_subject_ids:   set[int]
    failed_subject_ids:   set[int]
    enrolled_subject_ids: set[int]
    id_to_status:         dict[int, str]
    id_to_final_grade:    dict[int, Optional[float]]
    failed_entries:       list[tuple]   # list of (GradebookEntry, CurriculumSubject)


def _build_student_snapshot(
    db: Session,
    student_account_id: int,
) -> StudentSnapshot:

    rows = (
        db.query(GradebookEntry, CurriculumSubject)
        .join(CurriculumSubject, GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id)
        .filter(GradebookEntry.student_account_id == student_account_id)
        .all()
    )

    passed   : set[int] = set()
    failed   : set[int] = set()
    enrolled : set[int] = set()
    id_to_status:      dict[int, str]            = {}
    id_to_final_grade: dict[int, Optional[float]] = {}
    failed_entries: list[tuple] = []

    for entry, subject in rows:
        sid = entry.curriculum_subject_id
        id_to_status[sid]      = entry.completion_status
        id_to_final_grade[sid] = entry.final_grade

        if entry.completion_status == "PASSED":
            passed.add(sid)
        elif entry.completion_status == "FAILED":
            failed.add(sid)
            failed_entries.append((entry, subject))
        elif entry.completion_status in ("IN PROGRESS", "INCOMPLETE", "ENROLLED"):
            enrolled.add(sid)

    return StudentSnapshot(
        passed_subject_ids=passed,
        failed_subject_ids=failed,
        enrolled_subject_ids=enrolled,
        id_to_status=id_to_status,
        id_to_final_grade=id_to_final_grade,
        failed_entries=failed_entries,
    )


# ── Core check function ───────────────────────────────────────────────────────

def _check_one_subject(
    subject: CurriculumSubject,
    snapshot: StudentSnapshot,
    prereq_subject: Optional[CurriculumSubject],
) -> SubjectCheckResult:

    sid          = subject.subject_id
    subject_type = classify_subject(subject)

    # ── Already passed ────────────────────────────────────────────────────────
    if sid in snapshot.passed_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            subject_type=subject_type,
            status=ALREADY_COMPLETED,
            blocking_reason="Student already passed this subject.",
        )

    # ── Currently enrolled ────────────────────────────────────────────────────
    if sid in snapshot.enrolled_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            subject_type=subject_type,
            status=CURRENTLY_ENROLLED,
            blocking_reason="Student is currently enrolled in this subject.",
        )

    # ── No prerequisite → AVAILABLE ───────────────────────────────────────────
    if subject.prerequisite_subject_id is None:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            subject_type=subject_type,
            status=AVAILABLE,
        )

    # ── Has prerequisite — evaluate it ────────────────────────────────────────
    prereq_id    = subject.prerequisite_subject_id
    prereq_code  = prereq_subject.subject_code  if prereq_subject else str(prereq_id)
    prereq_title = prereq_subject.subject_title if prereq_subject else "Unknown"

    if prereq_id in snapshot.passed_subject_ids:
        return SubjectCheckResult(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            subject_type=subject_type,
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
            subject_type=subject_type,
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
            subject_type=subject_type,
            status=BLOCKED,
            prereq_code=prereq_code,
            prereq_title=prereq_title,
            prereq_status="FAILED",
            blocking_reason=(
                f"Prerequisite '{prereq_code} — {prereq_title}' was FAILED. "
                f"Add it as a back subject and pass it before taking this."
            ),
        )

    # Prereq was never taken
    return SubjectCheckResult(
        subject_id=sid,
        subject_code=subject.subject_code,
        subject_title=subject.subject_title,
        credit_units=subject.credit_units,
        subject_type=subject_type,
        status=BLOCKED,
        prereq_code=prereq_code,
        prereq_title=prereq_title,
        prereq_status="NOT TAKEN",
        blocking_reason=(
            f"Prerequisite '{prereq_code} — {prereq_title}' has not been "
            f"taken yet. It must be passed before this subject."
        ),
    )


# ── Back subjects builder ─────────────────────────────────────────────────────

def _build_back_subjects(snapshot: StudentSnapshot) -> list[BackSubjectRecord]:
    """
    Returns all failed subjects that the student should retake.
    Excludes subjects already being retaken (enrolled).
    """
    # Count failures per subject_id (strike counter)
    strike_counter: dict[int, int] = {}
    for entry, subject in snapshot.failed_entries:
        sid = entry.curriculum_subject_id
        strike_counter[sid] = strike_counter.get(sid, 0) + 1

    seen: set[int] = set()
    back_subjects: list[BackSubjectRecord] = []

    for entry, subject in snapshot.failed_entries:
        sid = entry.curriculum_subject_id

        # Skip if already re-enrolled for retake
        if sid in snapshot.enrolled_subject_ids:
            continue
        # Skip duplicates (multiple fail records for same subject)
        if sid in seen:
            continue
        seen.add(sid)

        subject_type = classify_subject(subject)
        times_failed = strike_counter.get(sid, 1)

        if subject_type == SUBJECT_SPECIAL:
            reason = (
                f"'{subject.subject_code}' is a special weekend program (NSTP/LTS/CWTS). "
                f"Students who do not pass in Year 1 must retake it in the next year level."
            )
        elif subject_type == SUBJECT_MAJOR:
            reason = (
                f"'{subject.subject_code}' is a MAJOR subject. "
                f"Advanced subjects that require it as a prerequisite are blocked until passed."
            )
        else:
            reason = (
                f"'{subject.subject_code}' is a MINOR/GE subject. "
                f"You may advance to next year, but it is recommended to retake it as extra load."
            )

        back_subjects.append(BackSubjectRecord(
            subject_id=sid,
            subject_code=subject.subject_code,
            subject_title=subject.subject_title,
            credit_units=subject.credit_units,
            subject_type=subject_type,
            times_failed=times_failed,
            blocking_reason=reason,
        ))

    # Sort: MAJOR first (most critical), then SPECIAL, then MINOR
    type_order = {SUBJECT_MAJOR: 0, SUBJECT_SPECIAL: 1, SUBJECT_MINOR: 2}
    back_subjects.sort(key=lambda b: type_order.get(b.subject_type, 3))
    return back_subjects


# ── Retention checker ─────────────────────────────────────────────────────────

def _check_retention(snapshot: StudentSnapshot) -> RetentionStatus:
    """
    Retention policy:
    - 3+ MAJOR subjects with final_grade of 3.0 → UNDER_RETENTION
    - 1-2 MAJOR subjects at 3.0                 → AT_RISK
    - Combined with multiple failures            → DROPOUT_RISK
    """
    at_risk_major_count = 0
    failed_units        = 0

    for entry, subject in snapshot.failed_entries:
        if classify_subject(subject) == SUBJECT_MAJOR:
            grade = entry.final_grade
            # 3.0 in Philippine grading = conditional pass / retention trigger
            if grade is not None:
                try:
                    if float(grade) >= 3.0:
                        at_risk_major_count += 1
                except (ValueError, TypeError):
                    pass
        failed_units += subject.credit_units

    total_failed = len(snapshot.failed_subject_ids)

    if at_risk_major_count >= 3 and total_failed > 3:
        status  = RETENTION_DROPOUT
        message = (
            f"HIGH RISK: Student has {at_risk_major_count} major subjects with a 3.0 grade "
            f"and {total_failed} total failed subjects. Student is UNDER RETENTION and at serious "
            f"risk of dropout. Requires mandatory academic counseling before enrollment is approved."
        )
    elif at_risk_major_count >= 3:
        status  = RETENTION_UNDER
        message = (
            f"WARNING: Student has {at_risk_major_count} major subjects with a 3.0 grade. "
            f"Student is UNDER RETENTION. A retention exam is required to continue in the program. "
            f"Failing the retention exam may result in program transfer or dismissal."
        )
    elif at_risk_major_count > 0:
        status  = RETENTION_AT_RISK
        message = (
            f"NOTICE: Student has {at_risk_major_count} major subject(s) with a 3.0 grade. "
            f"One more will trigger the retention policy. Monitor academic performance closely."
        )
    else:
        status  = RETENTION_GOOD
        message = "Student is in good academic standing."

    return RetentionStatus(
        status=status,
        message=message,
        at_risk_major_count=at_risk_major_count,
        failed_units=failed_units,
    )


# ── Verdict builder ───────────────────────────────────────────────────────────

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

    sem_label  = {1: "1st", 2: "2nd", 3: "Summer"}.get(target_semester, str(target_semester))
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
    elif blocked > 0 and total > 0 and (blocked / total) < 0.5:
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
            f"Student should retake failed back subjects and re-enroll next semester."
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


# ── SE-05: Priority ranking for AVAILABLE subjects ────────────────────────────

def _compute_priority_scores(
    results: list[SubjectCheckResult],
    target_year: int,
    target_semester: int,
    all_subjects: list,
) -> list[SubjectCheckResult]:
    """
    Assigns priority_score (0-100) to each AVAILABLE subject.
    Factors:
      - Sequence alignment (40%): does the subject belong to the target semester?
      - Chain advancement value (30%): how many subjects depend on this one (unlocking power)?
      - Subject type priority (30%): MAJOR > SPECIAL > MINOR
    """
    # Build dependent-count map: subject_id -> number of subjects that require it
    dependents_count: dict[int, int] = {}
    for s in all_subjects:
        if s.prerequisite_subject_id is not None:
            pid = s.prerequisite_subject_id
            dependents_count[pid] = dependents_count.get(pid, 0) + 1
    max_dependents = max(dependents_count.values(), default=1)

    type_score = {SUBJECT_MAJOR: 100, SUBJECT_SPECIAL: 60, SUBJECT_MINOR: 30}

    updated = []
    for r in results:
        if r.status != AVAILABLE:
            updated.append(r)
            continue

        # Find the matching subject for year/sem info
        matched = next((s for s in all_subjects if s.subject_id == r.subject_id), None)
        if matched is None:
            updated.append(r)
            continue

        # Sequence alignment: exact match = 100, off by 1 sem = 60, off by more = 20
        sem_diff = abs((matched.target_year_level * 2 + matched.target_semester) -
                       (target_year * 2 + target_semester))
        if sem_diff == 0:
            seq_score = 100
        elif sem_diff == 1:
            seq_score = 60
        elif sem_diff == 2:
            seq_score = 30
        else:
            seq_score = 10

        # Chain advancement: more dependents = higher value
        dep_count = dependents_count.get(r.subject_id, 0)
        chain_score = round((dep_count / max_dependents) * 100) if max_dependents > 0 else 0

        # Type priority
        t_score = type_score.get(r.subject_type, 30)

        priority = round(seq_score * 0.40 + chain_score * 0.30 + t_score * 0.30)
        updated.append(SubjectCheckResult(
            subject_id=r.subject_id, subject_code=r.subject_code,
            subject_title=r.subject_title, credit_units=r.credit_units,
            status=r.status, subject_type=r.subject_type,
            prereq_code=r.prereq_code, prereq_title=r.prereq_title,
            prereq_status=r.prereq_status, blocking_reason=r.blocking_reason,
            priority_score=priority,
        ))

    # Sort AVAILABLE subjects by priority descending; non-available stay in place
    available = sorted([r for r in updated if r.status == AVAILABLE],
                       key=lambda r: r.priority_score or 0, reverse=True)
    non_available = [r for r in updated if r.status != AVAILABLE]
    return available + non_available


# ── Public API ────────────────────────────────────────────────────────────────

class PrerequisiteChecker:

    def __init__(
        self,
        db: Session,
        ojt_subject_code: Optional[str] = None,
        student_ojt_clearance: str = "NOT_REQUIRED",
    ) -> None:
        self._db                    = db
        self._ojt_subject_code      = ojt_subject_code
        self._student_ojt_clearance = student_ojt_clearance

    def _apply_ojt_gate(
        self,
        results: list[SubjectCheckResult],
    ) -> list[SubjectCheckResult]:
        """
        Overrides any non-completed OJT subject to BLOCKED when the student
        does not have Secretary clearance. No-op when ojt_subject_code is unset.
        """
        if not self._ojt_subject_code or self._student_ojt_clearance == "CLEARED":
            return results

        updated = []
        for r in results:
            if (
                r.subject_code == self._ojt_subject_code
                and r.status not in (ALREADY_COMPLETED, CURRENTLY_ENROLLED)
            ):
                updated.append(SubjectCheckResult(
                    subject_id=r.subject_id,
                    subject_code=r.subject_code,
                    subject_title=r.subject_title,
                    credit_units=r.credit_units,
                    subject_type=r.subject_type,
                    status=BLOCKED,
                    blocking_reason=(
                        "OJT clearance documents have not been verified by the Secretary. "
                        "Submit your MOA, parent consent form, and medical clearance to the "
                        "Secretariat office before enrolling in this subject."
                    ),
                ))
            else:
                updated.append(r)
        return updated

    def _load_prereq_subject(
        self, prereq_id: Optional[int]
    ) -> Optional[CurriculumSubject]:
        if prereq_id is None:
            return None
        return self._db.query(CurriculumSubject).filter(
            CurriculumSubject.subject_id == prereq_id
        ).first()

    # ── check_semester ───────────────────────────────────────────────────────

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

        # SE-05: rank AVAILABLE subjects
        all_subjects = self._db.query(CurriculumSubject).all()
        results = _compute_priority_scores(results, year, semester, all_subjects)

        # F-13.1: OJT gate
        results = self._apply_ojt_gate(results)

        return _build_recommendation(results, year, semester)

    # ── check_subjects ───────────────────────────────────────────────────────

    def check_subjects(
        self,
        student_account_id: int,
        subject_codes: list[str],
    ) -> RecommendationResult:

        if not subject_codes:
            return _build_recommendation([], 0, 0)

        snapshot = _build_student_snapshot(self._db, student_account_id)

        subjects_found = (
            self._db.query(CurriculumSubject)
            .filter(CurriculumSubject.subject_code.in_(subject_codes))
            .all()
        )
        subject_map = {s.subject_code: s for s in subjects_found}

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

        results:    list[SubjectCheckResult] = []
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
                    subject_type=SUBJECT_MINOR,
                    status=BLOCKED,
                    blocking_reason=(
                        f"Subject code '{code}' was not found in the curriculum database."
                    ),
                ))
                continue

            prereq = prereq_map.get(subject.prerequisite_subject_id)
            results.append(_check_one_subject(subject, snapshot, prereq))
            year_levels.append(subject.target_year_level)
            semesters.append(subject.target_semester)

        target_year = max(year_levels) if year_levels else 0
        target_sem  = max(semesters)   if semesters   else 0

        # F-13.1: OJT gate
        results = self._apply_ojt_gate(results)

        return _build_recommendation(results, target_year, target_sem)

    # ── next_semester ────────────────────────────────────────────────────────

    def next_semester(
        self,
        student_account_id: int,
        current_year: int,
        current_semester: int,
    ) -> RecommendationResult:

        if current_semester == 1:
            next_year, next_sem = current_year, 2
        elif current_semester == 2:
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
            next_year, next_sem = current_year, current_semester + 1

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

    # ── Academic standing snapshot ────────────────────────────────────────────

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

            if entry.completion_status in ("IN PROGRESS", "ENROLLED", "NOT STARTED"):
                current_subjects.append(record)
            elif entry.completion_status == "PASSED":
                passed_subjects.append(record)

        passed_subjects.sort(
            key=lambda r: (r["target_year_level"], r["target_semester"], r["subject_code"])
        )
        current_subjects.sort(key=lambda r: r["subject_code"])

        # Build enriched data
        snapshot         = _build_student_snapshot(self._db, student_account_id)
        back_subjects    = _build_back_subjects(snapshot)
        retention_status = _check_retention(snapshot)
        is_irregular     = len(snapshot.failed_subject_ids) > 0

        next_rec = self.next_semester(
            student_account_id, current_year, current_semester
        )

        return {
            "current_subjects":             current_subjects,
            "passed_subjects":              passed_subjects,
            "next_semester_recommendation": next_rec,
            "back_subjects":                back_subjects,
            "retention_status":             retention_status,
            "is_irregular":                 is_irregular,
        }