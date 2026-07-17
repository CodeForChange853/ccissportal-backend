from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class EquipmentCreate(BaseModel):
    asset_tag:      str           = Field(..., max_length=100)
    equipment_name: str           = Field(..., max_length=255)
    category:       str           = Field(default="HARDWARE", max_length=30)
    quantity_total: int           = Field(..., ge=1)
    description:    str | None = Field(None, max_length=500)


class EquipmentUpdate(BaseModel):
    equipment_name: str | None = Field(None, max_length=255)
    category:       str | None = Field(None, max_length=30)
    quantity_total: int | None = Field(None, ge=1)
    description:    str | None = Field(None, max_length=500)
    is_active:      bool | None = None


class EquipmentResponse(BaseModel):
    id:                 int
    asset_tag:          str
    equipment_name:     str
    category:           str
    quantity_total:     int
    quantity_available: int
    description:        str | None = None
    is_active:          bool
    created_at:         datetime

    model_config = ConfigDict(from_attributes=True)


class CheckoutCreate(BaseModel):
    equipment_id:        int | None = None
    borrower_account_id: int
    borrower_type:       str           = Field(default="STUDENT", description="STUDENT or FACULTY")
    expected_return_at:  datetime | None = None
    checkout_notes:      str | None = Field(None, max_length=500)


class CheckoutReturnUpdate(BaseModel):
    checkout_notes: str | None = Field(None, max_length=500)


class CheckoutResponse(BaseModel):
    id:                        int
    equipment_id:              int
    borrower_account_id:       int
    borrower_type:             str
    checked_out_at:            datetime
    expected_return_at:        datetime | None = None
    actual_return_at:          datetime | None = None
    status:                    str
    checkout_notes:            str | None = None
    processed_by_secretary_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class FlagUnclearedResult(BaseModel):
    students_flagged:         int
    checkouts_marked_overdue: int


class EquipmentClearanceResponse(BaseModel):
    student_account_id:        int
    equipment_clearance_status: str
    active_checkouts:          int
    overdue_checkouts:         int
