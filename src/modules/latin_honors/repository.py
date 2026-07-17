from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from src.modules.faculty.models import GradebookEntry
from src.modules.enrollment.models import CurriculumSubject, StudentProfile
from src.modules.latin_honors.models import DeanNote, HonorsRating

SUMMA_MAX = 1.20
MAGNA_MAX = 1.45
CUM_LAUDE_MAX = 1.75


def _compute_student_gwas(db: Session) -> dict:
    rows = (
        db.query(
            GradebookEntry.student_account_id,
            func.sum(GradebookEntry.final_grade * CurriculumSubject.credit_units).label("weighted_sum"),
            func.sum(CurriculumSubject.credit_units).label("total_units"),
        )
        .join(CurriculumSubject, GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id)
        .filter(
            GradebookEntry.completion_status.in_(["COMPLETED", "PASSED"]),
            GradebookEntry.final_grade.isnot(None),
            GradebookEntry.final_grade <= 3.0,
        )
        .group_by(GradebookEntry.student_account_id)
        .all()
    )

    result = {}
    for row in rows:
        if row.total_units and row.total_units > 0:
            gwa = round(row.weighted_sum / row.total_units, 4)
            result[row.student_account_id] = gwa
    return result


def _get_rating_stats(db: Session, student_id: int) -> tuple[float, int]:
    r = (
        db.query(
            func.avg(HonorsRating.rating).label("avg"),
            func.count(HonorsRating.id).label("cnt"),
        )
        .filter(HonorsRating.student_account_id == student_id)
        .first()
    )
    return (round(float(r.avg or 0), 1), r.cnt or 0)


def _tier(gwa: float) -> str:
    if gwa <= SUMMA_MAX:
        return "SUMMA_CUM_LAUDE"
    if gwa <= MAGNA_MAX:
        return "MAGNA_CUM_LAUDE"
    return "CUM_LAUDE"


def get_honors_students(db: Session, course_filter: Optional[str] = None) -> list:
    gwa_map = _compute_student_gwas(db)
    qualifying = {sid: gwa for sid, gwa in gwa_map.items() if gwa <= CUM_LAUDE_MAX}
    if not qualifying:
        return []

    q = db.query(StudentProfile).filter(
        StudentProfile.student_account_id.in_(qualifying.keys()),
        StudentProfile.current_year_level == 4,
    )
    if course_filter:
        q = q.filter(StudentProfile.current_course.ilike(f"%{course_filter}%"))

    results = []
    for p in q.all():
        gwa = qualifying[p.student_account_id]
        note = db.query(DeanNote).filter(DeanNote.student_account_id == p.student_account_id).first()
        avg_r, cnt = _get_rating_stats(db, p.student_account_id)
        results.append({
            "student_account_id": p.student_account_id,
            "full_name": f"{p.first_name} {p.last_name}",
            "course": p.current_course or "N/A",
            "year_level": p.current_year_level,
            "gwa": gwa,
            "honor_tier": _tier(gwa),
            "dean_note": note.message if note else None,
            "avg_rating": avg_r,
            "rating_count": cnt,
        })

    results.sort(key=lambda x: x["gwa"])
    return results


def get_running_for_honors(db: Session) -> list:
    gwa_map = _compute_student_gwas(db)
    qualifying = {sid: gwa for sid, gwa in gwa_map.items() if gwa <= CUM_LAUDE_MAX}
    if not qualifying:
        return []

    profiles = (
        db.query(StudentProfile)
        .filter(
            StudentProfile.student_account_id.in_(qualifying.keys()),
            StudentProfile.current_year_level.in_([1, 2, 3]),
        )
        .all()
    )

    results = [
        {
            "full_name": f"{p.first_name} {p.last_name}",
            "course": p.current_course or "N/A",
            "year_level": p.current_year_level,
            "gwa": qualifying[p.student_account_id],
        }
        for p in profiles
    ]
    results.sort(key=lambda x: x["gwa"])
    return results


def get_all_departments(db: Session) -> list:
    rows = (
        db.query(StudentProfile.current_course)
        .filter(StudentProfile.current_course.isnot(None))
        .distinct()
        .all()
    )
    return sorted([r.current_course for r in rows if r.current_course])


def upsert_dean_note(db: Session, student_account_id: int, message: str, admin_id: int):
    existing = db.query(DeanNote).filter(DeanNote.student_account_id == student_account_id).first()
    if existing:
        existing.message = message
        existing.written_by_admin_id = admin_id
        db.commit()
        return existing
    note = DeanNote(student_account_id=student_account_id, message=message, written_by_admin_id=admin_id)
    db.add(note)
    db.commit()
    return note


def delete_dean_note(db: Session, student_account_id: int):
    db.query(DeanNote).filter(DeanNote.student_account_id == student_account_id).delete()
    db.commit()


def submit_rating(db: Session, student_account_id: int, session_token: str, rating: int) -> dict:
    existing = db.query(HonorsRating).filter(
        HonorsRating.student_account_id == student_account_id,
        HonorsRating.rater_session_token == session_token,
    ).first()
    if existing:
        existing.rating = rating
        db.commit()
    else:
        db.add(HonorsRating(
            student_account_id=student_account_id,
            rater_session_token=session_token,
            rating=rating,
        ))
        db.commit()
    avg_r, cnt = _get_rating_stats(db, student_account_id)
    return {"avg_rating": avg_r, "rating_count": cnt}


def get_admin_honors_list(db: Session) -> list:
    gwa_map = _compute_student_gwas(db)
    qualifying = {sid: gwa for sid, gwa in gwa_map.items() if gwa <= CUM_LAUDE_MAX}
    if not qualifying:
        return []

    profiles = (
        db.query(StudentProfile)
        .filter(
            StudentProfile.student_account_id.in_(qualifying.keys()),
            StudentProfile.current_year_level == 4,
        )
        .all()
    )

    results = []
    for p in profiles:
        gwa = qualifying[p.student_account_id]
        note = db.query(DeanNote).filter(DeanNote.student_account_id == p.student_account_id).first()
        results.append({
            "student_account_id": p.student_account_id,
            "full_name": f"{p.first_name} {p.last_name}",
            "course": p.current_course or "N/A",
            "year_level": p.current_year_level,
            "gwa": gwa,
            "honor_tier": _tier(gwa),
            "has_note": note is not None,
            "current_note": note.message if note else None,
        })

    results.sort(key=lambda x: x["gwa"])
    return results
