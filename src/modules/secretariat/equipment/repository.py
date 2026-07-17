from datetime import datetime, timezone
from sqlalchemy.orm import Session
from . import models


def save_equipment(db: Session, item: models.EquipmentInventory) -> models.EquipmentInventory:
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def fetch_all_equipment(db: Session, active_only: bool = False) -> list[models.EquipmentInventory]:
    query = db.query(models.EquipmentInventory)
    if active_only:
        query = query.filter(models.EquipmentInventory.is_active == True)
    return query.order_by(models.EquipmentInventory.asset_tag).all()


def fetch_equipment_by_id(db: Session, equipment_id: int) -> models.EquipmentInventory | None:
    return (
        db.query(models.EquipmentInventory)
        .filter(models.EquipmentInventory.id == equipment_id)
        .first()
    )


def save_checkout(db: Session, checkout: models.EquipmentCheckout) -> models.EquipmentCheckout:
    db.add(checkout)
    db.commit()
    db.refresh(checkout)
    return checkout


def fetch_checkout_by_id(db: Session, checkout_id: int) -> models.EquipmentCheckout | None:
    return (
        db.query(models.EquipmentCheckout)
        .filter(models.EquipmentCheckout.id == checkout_id)
        .first()
    )


def fetch_active_checkouts(db: Session) -> list[models.EquipmentCheckout]:
    return (
        db.query(models.EquipmentCheckout)
        .filter(models.EquipmentCheckout.status.in_(["CHECKED_OUT", "OVERDUE"]))
        .order_by(models.EquipmentCheckout.checked_out_at.asc())
        .all()
    )


def fetch_overdue_checkouts(db: Session) -> list[models.EquipmentCheckout]:
    now = datetime.now(timezone.utc)
    return (
        db.query(models.EquipmentCheckout)
        .filter(
            models.EquipmentCheckout.status == "CHECKED_OUT",
            models.EquipmentCheckout.expected_return_at != None,
            models.EquipmentCheckout.expected_return_at < now,
        )
        .all()
    )


def fetch_checkouts_for_borrower(
    db: Session,
    borrower_id: int,
    active_only: bool = True,
) -> list[models.EquipmentCheckout]:
    query = db.query(models.EquipmentCheckout).filter(
        models.EquipmentCheckout.borrower_account_id == borrower_id
    )
    if active_only:
        query = query.filter(models.EquipmentCheckout.status.in_(["CHECKED_OUT", "OVERDUE"]))
    return query.all()
