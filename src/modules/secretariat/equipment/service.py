from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas, repository
from src.modules.enrollment.models import StudentProfile
from src.modules.audit import service as audit_service


def add_equipment(db: Session, data: schemas.EquipmentCreate) -> models.EquipmentInventory:
    item = models.EquipmentInventory(
        asset_tag=data.asset_tag,
        equipment_name=data.equipment_name,
        category=data.category,
        quantity_total=data.quantity_total,
        quantity_available=data.quantity_total,
        description=data.description,
    )
    return repository.save_equipment(db, item)


def update_equipment(
    db: Session,
    equipment_id: int,
    data: schemas.EquipmentUpdate,
) -> models.EquipmentInventory:
    item = repository.fetch_equipment_by_id(db, equipment_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found.")

    update_dict = data.model_dump(exclude_none=True)
    if "quantity_total" in update_dict:
        delta = update_dict["quantity_total"] - item.quantity_total
        item.quantity_available = max(0, item.quantity_available + delta)
    for key, value in update_dict.items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item


def checkout_equipment(
    db: Session,
    data: schemas.CheckoutCreate,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.EquipmentCheckout:
    if not data.equipment_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="equipment_id is required.")
    item = repository.fetch_equipment_by_id(db, data.equipment_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found.")
    if not item.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This equipment item is no longer active.",
        )
    if item.quantity_available < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No units of '{item.equipment_name}' are currently available for checkout.",
        )

    checkout = models.EquipmentCheckout(
        equipment_id=data.equipment_id,
        borrower_account_id=data.borrower_account_id,
        borrower_type=data.borrower_type,
        expected_return_at=data.expected_return_at,
        checkout_notes=data.checkout_notes,
        status="CHECKED_OUT",
        processed_by_secretary_id=secretary_id,
    )
    item.quantity_available -= 1
    db.add(checkout)
    db.commit()
    db.refresh(checkout)

    audit_service.log_event(
        database_session=db,
        event_type="EQUIPMENT_CHECKED_OUT",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="equipment_checkout",
        target_id=checkout.id,
        ip_address=ip_address,
        payload={
            "equipment_id":   data.equipment_id,
            "equipment_name": item.equipment_name,
            "borrower_id":    data.borrower_account_id,
            "borrower_type":  data.borrower_type,
        },
    )
    return checkout


def return_equipment(
    db: Session,
    checkout_id: int,
    data: schemas.CheckoutReturnUpdate,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.EquipmentCheckout:
    checkout = repository.fetch_checkout_by_id(db, checkout_id)
    if not checkout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkout record not found.")
    if checkout.status == "RETURNED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This item has already been returned.",
        )

    checkout.actual_return_at = datetime.now(timezone.utc)
    checkout.status = "RETURNED"
    if data.checkout_notes:
        checkout.checkout_notes = data.checkout_notes

    item = repository.fetch_equipment_by_id(db, checkout.equipment_id)
    if item:
        item.quantity_available = min(item.quantity_total, item.quantity_available + 1)

    remaining = repository.fetch_checkouts_for_borrower(db, checkout.borrower_account_id, active_only=True)
    remaining = [c for c in remaining if c.id != checkout_id]

    if not remaining and checkout.borrower_type == "STUDENT":
        profile = db.query(StudentProfile).filter(
            StudentProfile.student_account_id == checkout.borrower_account_id
        ).first()
        if profile and profile.equipment_clearance_status == "UNCLEARED":
            profile.equipment_clearance_status = "CLEARED"

    db.commit()
    db.refresh(checkout)

    audit_service.log_event(
        database_session=db,
        event_type="EQUIPMENT_RETURNED",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="equipment_checkout",
        target_id=checkout_id,
        ip_address=ip_address,
        payload={
            "equipment_id": checkout.equipment_id,
            "borrower_id":  checkout.borrower_account_id,
            "auto_cleared": not remaining,
        },
    )
    return checkout


def flag_uncleared_students(
    db: Session,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> schemas.FlagUnclearedResult:
    overdue = repository.fetch_overdue_checkouts(db)
    if not overdue:
        return schemas.FlagUnclearedResult(students_flagged=0, checkouts_marked_overdue=0)

    student_ids_flagged: set[int] = set()
    for checkout in overdue:
        checkout.status = "OVERDUE"
        if checkout.borrower_type == "STUDENT":
            student_ids_flagged.add(checkout.borrower_account_id)

    for student_id in student_ids_flagged:
        profile = db.query(StudentProfile).filter(
            StudentProfile.student_account_id == student_id
        ).first()
        if profile:
            profile.equipment_clearance_status = "UNCLEARED"

    db.commit()

    audit_service.log_event(
        database_session=db,
        event_type="EQUIPMENT_FLAGGED_UNCLEARED",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="batch",
        ip_address=ip_address,
        payload={
            "students_flagged":         len(student_ids_flagged),
            "checkouts_marked_overdue": len(overdue),
        },
    )
    return schemas.FlagUnclearedResult(
        students_flagged=len(student_ids_flagged),
        checkouts_marked_overdue=len(overdue),
    )


def manually_clear_student_equipment(
    db: Session,
    student_id: int,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> schemas.EquipmentClearanceResponse:
    profile = db.query(StudentProfile).filter(
        StudentProfile.student_account_id == student_id
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    profile.equipment_clearance_status = "CLEARED"
    db.commit()

    audit_service.log_event(
        database_session=db,
        event_type="EQUIPMENT_MANUALLY_CLEARED",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="student",
        target_id=student_id,
        ip_address=ip_address,
        payload={"student_id": student_id},
    )

    active_checkouts = repository.fetch_checkouts_for_borrower(db, student_id, active_only=True)
    overdue = [c for c in active_checkouts if c.status == "OVERDUE"]

    return schemas.EquipmentClearanceResponse(
        student_account_id=student_id,
        equipment_clearance_status="CLEARED",
        active_checkouts=len(active_checkouts),
        overdue_checkouts=len(overdue),
    )


def get_equipment_clearance_status(db: Session, student_id: int) -> schemas.EquipmentClearanceResponse:
    profile = db.query(StudentProfile).filter(
        StudentProfile.student_account_id == student_id
    ).first()
    clearance = profile.equipment_clearance_status if profile else "CLEARED"

    active_checkouts = repository.fetch_checkouts_for_borrower(db, student_id, active_only=True)
    overdue = [c for c in active_checkouts if c.status == "OVERDUE"]

    return schemas.EquipmentClearanceResponse(
        student_account_id=student_id,
        equipment_clearance_status=clearance,
        active_checkouts=len(active_checkouts),
        overdue_checkouts=len(overdue),
    )
