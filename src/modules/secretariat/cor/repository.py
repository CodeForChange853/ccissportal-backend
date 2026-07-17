from datetime import datetime, timezone
from sqlalchemy.orm import Session


def fetch_cor_queue(db: Session, cor_status: str | None = None):
    from src.modules.enrollment.models import StudentEnrollmentRequest as _Req
    query = db.query(_Req).filter(_Req.review_status == "APPROVED")
    if cor_status and cor_status != "ALL":
        query = query.filter(_Req.cor_release_status == cor_status)
    return query.order_by(_Req.date_submitted.desc()).all()


def release_cor_for_request(db: Session, request_id: int, secretary_id: int):
    from src.modules.enrollment.models import StudentEnrollmentRequest as _Req
    req = db.query(_Req).filter(_Req.request_id == request_id).first()
    if not req:
        return None
    req.cor_release_status            = "RELEASED"
    req.cor_released_at               = datetime.now(timezone.utc)
    req.cor_released_by_secretary_id  = secretary_id
    db.commit()
    db.refresh(req)
    return req
