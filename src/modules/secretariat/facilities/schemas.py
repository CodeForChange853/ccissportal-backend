from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date


class StudentOrganizationCreate(BaseModel):
    org_name:             str           = Field(..., max_length=255)
    org_acronym:          str | None = Field(None, max_length=20)
    org_type:             str           = Field(default="OTHER", description="ACADEMIC | CULTURAL | SPORTS | RELIGIOUS | SERVICE | OTHER")
    description:          str | None = Field(None, max_length=2000)
    adviser_account_id:   int | None = None
    president_account_id: int | None = None


class OrgProcessDecision(BaseModel):
    decision:        str           = Field(..., description="RECOGNIZE | SUSPEND | DISSOLVE")
    secretary_notes: str | None = Field(None, max_length=500)


class StudentOrganizationResponse(BaseModel):
    id:                      int
    org_name:                str
    org_acronym:             str | None      = None
    org_type:                str
    description:             str | None      = None
    adviser_account_id:      int | None      = None
    president_account_id:    int | None      = None
    submitted_by_account_id: int
    status:                  str
    secretary_notes:         str | None      = None
    processed_by:            int | None      = None
    processed_at:            datetime | None = None
    created_at:              datetime

    model_config = ConfigDict(from_attributes=True)


class FacilityCreate(BaseModel):
    facility_code: str           = Field(..., max_length=30)
    facility_name: str           = Field(..., max_length=255)
    facility_type: str           = Field(default="ROOM", description="ROOM | LAB | AUDITORIUM | GYMNASIUM | FIELD | OTHER")
    building:      str | None = Field(None, max_length=100)
    capacity:      int | None = Field(None, ge=1)
    description:   str | None = Field(None, max_length=500)


class FacilityUpdate(BaseModel):
    facility_name: str | None  = Field(None, max_length=255)
    facility_type: str | None  = Field(None, max_length=30)
    building:      str | None  = Field(None, max_length=100)
    capacity:      int | None  = Field(None, ge=1)
    description:   str | None  = Field(None, max_length=500)
    is_bookable:   bool | None = None


class FacilityResponse(BaseModel):
    id:            int
    facility_code: str
    facility_name: str
    facility_type: str
    building:      str | None = None
    capacity:      int | None = None
    description:   str | None = None
    is_bookable:   bool
    created_at:    datetime

    model_config = ConfigDict(from_attributes=True)


class FacilityBookingCreate(BaseModel):
    facility_id:       int
    org_id:            int | None = None
    event_title:       str           = Field(..., max_length=255)
    event_description: str | None = Field(None, max_length=2000)
    booking_date:      date
    time_start:        datetime
    time_end:          datetime
    attendee_count:    int | None = Field(None, ge=1)


class BookingProcessDecision(BaseModel):
    decision:         str           = Field(..., description="APPROVE | REJECT")
    secretary_notes:  str | None = Field(None, max_length=500)
    rejection_reason: str | None = Field(None, max_length=500)


class FacilityBookingResponse(BaseModel):
    id:                        int
    facility_id:               int
    requestor_account_id:      int
    org_id:                    int | None      = None
    event_title:               str
    event_description:         str | None      = None
    booking_date:              date
    time_start:                datetime
    time_end:                  datetime
    attendee_count:            int | None      = None
    status:                    str
    secretary_notes:           str | None      = None
    processed_by_secretary_id: int | None      = None
    processed_at:              datetime | None = None
    rejection_reason:          str | None      = None
    cancelled_at:              datetime | None = None
    created_at:                datetime

    model_config = ConfigDict(from_attributes=True)
