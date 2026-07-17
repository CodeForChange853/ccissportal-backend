from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from src.core.database_setup import Base


class EquipmentInventory(Base):
    __tablename__ = "equipment_inventory"

    id                 = Column(Integer, primary_key=True, index=True)
    asset_tag          = Column(String(100), unique=True, index=True, nullable=False)
    equipment_name     = Column(String(255), nullable=False)
    category           = Column(String(30), nullable=False, default="HARDWARE")
    quantity_total     = Column(Integer, nullable=False, default=1)
    quantity_available = Column(Integer, nullable=False, default=1)
    description        = Column(String(500), nullable=True)
    is_active          = Column(Boolean, nullable=False, default=True)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())


class EquipmentCheckout(Base):
    __tablename__ = "equipment_checkouts"

    id           = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment_inventory.id"), index=True, nullable=False)
    borrower_account_id = Column(Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False)
    # STUDENT | FACULTY
    borrower_type = Column(String(20), nullable=False, default="STUDENT")

    checked_out_at     = Column(DateTime(timezone=True), server_default=func.now())
    expected_return_at = Column(DateTime(timezone=True), nullable=True)
    actual_return_at   = Column(DateTime(timezone=True), nullable=True)

    # CHECKED_OUT | RETURNED | OVERDUE
    status = Column(String(20), nullable=False, default="CHECKED_OUT", index=True)

    checkout_notes             = Column(String(500), nullable=True)
    processed_by_secretary_id  = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
