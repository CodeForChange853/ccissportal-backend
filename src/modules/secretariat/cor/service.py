from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import schemas, repository


def get_cor_queue(db: Session, cor_status: Optional[str] = None) -> list[schemas.CORQueueItem]:
    from src.modules.enrollment.models import StudentProfile
    reqs = repository.fetch_cor_queue(db, cor_status=cor_status)
    if not reqs:
        return []

    student_ids = [r.student_account_id for r in reqs]
    profiles    = db.query(StudentProfile).filter(
        StudentProfile.student_account_id.in_(student_ids)
    ).all()
    profile_map = {p.student_account_id: p for p in profiles}

    result = []
    for req in reqs:
        profile = profile_map.get(req.student_account_id)
        result.append(schemas.CORQueueItem(
            request_id=                   req.request_id,
            student_account_id=           req.student_account_id,
            student_name=                 f"{profile.first_name} {profile.last_name}".strip() if profile else None,
            student_number=               profile.student_number if profile else None,
            target_year_level=            req.target_year_level,
            target_semester=              req.target_semester,
            extracted_subjects=           req.extracted_subjects,
            review_status=                req.review_status,
            cor_release_status=           req.cor_release_status,
            cor_released_at=              req.cor_released_at,
            cor_released_by_secretary_id= req.cor_released_by_secretary_id,
            date_submitted=               req.date_submitted,
        ))
    return result


def release_cor(db: Session, request_id: int, secretary_id: int) -> schemas.CORQueueItem:
    from src.modules.enrollment.models import StudentProfile
    req = repository.release_cor_for_request(db, request_id=request_id, secretary_id=secretary_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment request not found.")
    if req.review_status != "APPROVED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="COR can only be released for APPROVED enrollments.")

    profile = db.query(StudentProfile).filter(
        StudentProfile.student_account_id == req.student_account_id
    ).first()

    return schemas.CORQueueItem(
        request_id=                   req.request_id,
        student_account_id=           req.student_account_id,
        student_name=                 f"{profile.first_name} {profile.last_name}".strip() if profile else None,
        student_number=               profile.student_number if profile else None,
        target_year_level=            req.target_year_level,
        target_semester=              req.target_semester,
        extracted_subjects=           req.extracted_subjects,
        review_status=                req.review_status,
        cor_release_status=           req.cor_release_status,
        cor_released_at=              req.cor_released_at,
        cor_released_by_secretary_id= req.cor_released_by_secretary_id,
        date_submitted=               req.date_submitted,
    )
