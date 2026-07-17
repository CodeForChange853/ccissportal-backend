from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.database_setup import get_database_session
from src.core.security import require_admin
from src.modules.latin_honors import service
from src.modules.latin_honors.schemas import (
    DeanNoteRequest, GenerateNoteRequest, RatingRequest,
)

honors_router = APIRouter(prefix="/latin-honors", tags=["Latin Honors"])


@honors_router.get("/global")
def get_global_honors(db: Session = Depends(get_database_session)):
    return service.get_global_honors(db)


@honors_router.get("/departments")
def get_departments(db: Session = Depends(get_database_session)):
    from src.modules.latin_honors.repository import get_all_departments
    return get_all_departments(db)


@honors_router.get("/running")
def get_running_for_honors(db: Session = Depends(get_database_session)):
    return service.get_running_for_honors(db)


@honors_router.get("/department/{course}")
def get_department_honors(course: str, db: Session = Depends(get_database_session)):
    return service.get_department_honors(db, course)


@honors_router.get("/admin/list")
def get_admin_honors_list(
    db: Session = Depends(get_database_session),
    _admin=Depends(require_admin),
):
    return service.get_admin_honors_list(db)


@honors_router.post("/{student_id}/rate")
def rate_student(
    student_id: int,
    body: RatingRequest,
    db: Session = Depends(get_database_session),
):
    try:
        return service.submit_rating(db, student_id, body.session_token, body.rating)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@honors_router.post("/dean-note")
def save_dean_note(
    body: DeanNoteRequest,
    db: Session = Depends(get_database_session),
    current_admin=Depends(require_admin),
):
    service.save_dean_note(db, body.student_account_id, body.message, current_admin.account_id)
    return {"status": "saved"}


@honors_router.delete("/dean-note/{student_id}")
def delete_dean_note(
    student_id: int,
    db: Session = Depends(get_database_session),
    _admin=Depends(require_admin),
):
    service.remove_dean_note(db, student_id)
    return {"status": "deleted"}


@honors_router.post("/generate-note")
def generate_ai_note(
    body: GenerateNoteRequest,
    _admin=Depends(require_admin),
):
    try:
        note = service.generate_ai_note(
            full_name=body.full_name,
            gwa=body.gwa,
            honor_tier=body.honor_tier,
            course=body.course,
        )
        return {"note": note}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
