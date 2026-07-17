# backend-v2/src/modules/enrollment/at_risk_engine.py
"""
SE-04 — Student At-Risk Early Warning System
Pure rule-based engine — zero Gemini / external API calls.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, List

from sqlalchemy.orm import Session

from src.modules.faculty.models import GradebookEntry, ConsultationRequest
from src.modules.enrollment.models import CurriculumSubject
from .prerequisite_checker import classify_subject, SUBJECT_MAJOR, SUBJECT_MINOR, SUBJECT_SPECIAL


# ── Risk level thresholds ─────────────────────────────────────────────────────
RISK_HIGH     = 70
RISK_MODERATE = 40


# ── Result data classes ───────────────────────────────────────────────────────

@dataclass
class AtRiskBreakdown:
    failed_load_score:   int   # 0–100  (weight 30%)
    gwa_score:           int   # 0–100  (weight 30%)
    variance_score:      int   # 0–100  (weight 20%)
    consultation_score:  int   # 0–100  (weight 20%)


@dataclass
class AtRiskAssessment:
    student_account_id:   int
    risk_score:           int
    risk_level:           str          # HIGH | MODERATE | LOW
    breakdown:            AtRiskBreakdown
    interventions:        List[str]
    gwa:                  Optional[float]
    failed_major_count:   int
    failed_minor_count:   int
    has_any_consultation: bool


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _failed_load_score(failed_major: int, failed_minor: int) -> int:
    return min(100, failed_major * 20 + failed_minor * 7)


def _gwa_score(gwa: Optional[float]) -> int:
    """
    Philippine scale — 1.0 (best) to 3.0 (borderline) to 5.0 (failed).
    Risk increases only above 3.0; perfect standing returns 0.
    """
    if gwa is None or gwa <= 3.0:
        return 0
    return min(100, round((gwa - 3.0) / 2.0 * 100))


def _variance_score(grades: list[float]) -> int:
    if len(grades) < 2:
        return 0
    mean    = sum(grades) / len(grades)
    std_dev = math.sqrt(sum((g - mean) ** 2 for g in grades) / len(grades))
    return min(100, round((std_dev / 1.5) * 100))


def _consultation_score(has_any: bool) -> int:
    return 0 if has_any else 100


def _risk_level(score: int) -> str:
    if score >= RISK_HIGH:
        return "HIGH"
    if score >= RISK_MODERATE:
        return "MODERATE"
    return "LOW"


# ── Rule-based intervention builder ──────────────────────────────────────────

def _build_interventions(
    failed_major_subjects: list,
    gwa:                  Optional[float],
    variance_score:       int,
    has_any_consultation: bool,
    retention_at_risk:    bool,
) -> list[str]:
    msgs: list[str] = []

    if retention_at_risk:
        msgs.append(
            "Retention policy applies — contact the Registrar immediately "
            "for mandatory academic counseling."
        )

    for subj in failed_major_subjects[:3]:
        msgs.append(
            f"Prioritize retaking {subj.subject_code} ({subj.subject_title}) — "
            f"it is blocking prerequisite-dependent subjects."
        )

    if gwa is not None and gwa > 3.0:
        msgs.append(
            f"Cumulative GWA of {gwa:.2f} exceeds the passing threshold of 3.0 — "
            f"seek academic mentoring or tutoring assistance."
        )

    if variance_score >= 50:
        msgs.append(
            "Significant performance inconsistency detected across subjects — "
            "identify weaker areas and establish a consistent study schedule."
        )

    if not has_any_consultation:
        msgs.append(
            "No consultation sessions have been booked — "
            "schedule a meeting with your instructor or academic advisor."
        )

    if not msgs:
        msgs.append(
            "No immediate interventions required — maintain current academic performance."
        )

    return msgs


# ── Public function ───────────────────────────────────────────────────────────

def assess_student_risk(
    db: Session,
    student_account_id: int,
) -> AtRiskAssessment:
    """
    Compute the at-risk composite score for one student.
    Four deterministic factors — no external API calls.
    """

    # ── 1. Load all grade records ─────────────────────────────────────────────
    rows = (
        db.query(GradebookEntry, CurriculumSubject)
        .join(CurriculumSubject, GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id)
        .filter(GradebookEntry.student_account_id == student_account_id)
        .all()
    )

    failed_majors:    list[CurriculumSubject] = []
    failed_minors:    list[CurriculumSubject] = []
    graded_rows:      list[tuple]             = []  # (entry, subject) with final_grade
    retention_at_risk = False

    seen_failed: set[int] = set()  # deduplicate per subject_id

    for entry, subject in rows:
        if entry.final_grade is not None:
            graded_rows.append((entry, subject))

        if entry.completion_status == "FAILED" and subject.subject_id not in seen_failed:
            seen_failed.add(subject.subject_id)
            stype = classify_subject(subject)
            if stype == SUBJECT_MAJOR:
                failed_majors.append(subject)
                if entry.final_grade is not None and float(entry.final_grade) >= 3.0:
                    retention_at_risk = True
            else:
                failed_minors.append(subject)

    # ── 2. Weighted GWA (Philippine scale 1.0–5.0) ───────────────────────────
    gwa: Optional[float] = None
    if graded_rows:
        total_points = sum(float(e.final_grade) * s.credit_units for e, s in graded_rows)
        total_units  = sum(s.credit_units for _, s in graded_rows)
        if total_units > 0:
            gwa = round(total_points / total_units, 2)

    final_grades = [float(e.final_grade) for e, _ in graded_rows]

    # ── 3. Consultation check ─────────────────────────────────────────────────
    has_any_consultation = (
        db.query(ConsultationRequest)
        .filter(
            ConsultationRequest.student_account_id == student_account_id,
            ConsultationRequest.status.in_(["APPROVED", "COMPLETED", "PENDING"]),
        )
        .first() is not None
    )

    # ── 4. Score factors ──────────────────────────────────────────────────────
    fl_score = _failed_load_score(len(failed_majors), len(failed_minors))
    gwa_s    = _gwa_score(gwa)
    var_s    = _variance_score(final_grades)
    con_s    = _consultation_score(has_any_consultation)

    composite = round(fl_score * 0.30 + gwa_s * 0.30 + var_s * 0.20 + con_s * 0.20)

    interventions = _build_interventions(
        failed_major_subjects=failed_majors,
        gwa=gwa,
        variance_score=var_s,
        has_any_consultation=has_any_consultation,
        retention_at_risk=retention_at_risk,
    )

    return AtRiskAssessment(
        student_account_id=student_account_id,
        risk_score=composite,
        risk_level=_risk_level(composite),
        breakdown=AtRiskBreakdown(
            failed_load_score=fl_score,
            gwa_score=gwa_s,
            variance_score=var_s,
            consultation_score=con_s,
        ),
        interventions=interventions,
        gwa=gwa,
        failed_major_count=len(failed_majors),
        failed_minor_count=len(failed_minors),
        has_any_consultation=has_any_consultation,
    )
