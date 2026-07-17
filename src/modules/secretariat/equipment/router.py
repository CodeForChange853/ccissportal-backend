from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import require_admin_or_secretary, get_current_user
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

equipment_router = APIRouter(prefix="/secretariat", tags=["Secretariat — Equipment"])


@equipment_router.get("/equipment", response_model=List[schemas.EquipmentResponse])
def list_equipment(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    return repository.fetch_all_equipment(db, active_only=active_only)


@equipment_router.post("/equipment", response_model=schemas.EquipmentResponse, status_code=status.HTTP_201_CREATED)
def create_equipment(
    data: schemas.EquipmentCreate,
    db: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin_or_secretary),
):
    return service.add_equipment(db=db, data=data)


@equipment_router.patch("/equipment/{equipment_id}", response_model=schemas.EquipmentResponse)
def update_equipment(
    equipment_id: int,
    data: schemas.EquipmentUpdate,
    db: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin_or_secretary),
):
    return service.update_equipment(db=db, equipment_id=equipment_id, data=data)


@equipment_router.post(
    "/equipment/{equipment_id}/checkout",
    response_model=schemas.CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def checkout_equipment(
    equipment_id: int,
    request: Request,
    data: schemas.CheckoutCreate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    data.equipment_id = equipment_id
    return service.checkout_equipment(
        db=db,
        data=data,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@equipment_router.patch("/equipment/checkout/{checkout_id}/return", response_model=schemas.CheckoutResponse)
def return_equipment(
    checkout_id: int,
    request: Request,
    data: schemas.CheckoutReturnUpdate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.return_equipment(
        db=db,
        checkout_id=checkout_id,
        data=data,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@equipment_router.get("/equipment/checkouts/active", response_model=List[schemas.CheckoutResponse])
def list_active_checkouts(
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    return repository.fetch_active_checkouts(db)


@equipment_router.get("/equipment/checkouts/overdue", response_model=List[schemas.CheckoutResponse])
def list_overdue_checkouts(
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    return repository.fetch_overdue_checkouts(db)


@equipment_router.post("/equipment/flag-uncleared", response_model=schemas.FlagUnclearedResult)
def flag_uncleared_students(
    request: Request,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.flag_uncleared_students(
        db=db,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@equipment_router.patch(
    "/equipment/clearance/{student_id}/clear",
    response_model=schemas.EquipmentClearanceResponse,
)
def manually_clear_student(
    student_id: int,
    request: Request,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.manually_clear_student_equipment(
        db=db,
        student_id=student_id,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@equipment_router.get("/equipment/clearance/my-status", response_model=schemas.EquipmentClearanceResponse)
def get_my_equipment_clearance(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_equipment_clearance_status(db=db, student_id=current_user.account_id)


@equipment_router.get("/equipment/clearance/{student_id}", response_model=schemas.EquipmentClearanceResponse)
def get_student_equipment_clearance(
    student_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    return service.get_equipment_clearance_status(db=db, student_id=student_id)
