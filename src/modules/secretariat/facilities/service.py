from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas, repository
from src.modules.audit import service as audit_service

_VALID_ORG_TYPES      = {"ACADEMIC", "CULTURAL", "SPORTS", "RELIGIOUS", "SERVICE", "OTHER"}
_VALID_FACILITY_TYPES = {"ROOM", "LAB", "AUDITORIUM", "GYMNASIUM", "FIELD", "OTHER"}


def register_organization(
    db: Session,
    requestor_id: int,
    data: schemas.StudentOrganizationCreate,
    ip_address: Optional[str] = None,
) -> models.StudentOrganization:
    if data.org_type not in _VALID_ORG_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid org_type. Must be one of: {', '.join(sorted(_VALID_ORG_TYPES))}.",
        )

    existing = repository.fetch_organization_by_name(db, data.org_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An organization named '{data.org_name}' already exists.",
        )

    org = models.StudentOrganization(
        org_name=data.org_name,
        org_acronym=data.org_acronym,
        org_type=data.org_type,
        description=data.description,
        adviser_account_id=data.adviser_account_id,
        president_account_id=data.president_account_id,
        submitted_by_account_id=requestor_id,
        status="PENDING",
    )
    saved = repository.save_organization(db, org)

    audit_service.log_event(
        database_session=db,
        event_type="ORG_REGISTRATION_SUBMITTED",
        actor_id=requestor_id,
        target_type="student_organization",
        target_id=saved.id,
        ip_address=ip_address,
        payload={"org_name": data.org_name, "org_type": data.org_type},
    )
    return saved


def process_org_registration(
    db: Session,
    org_id: int,
    data: schemas.OrgProcessDecision,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.StudentOrganization:
    if data.decision not in ("RECOGNIZE", "SUSPEND", "DISSOLVE"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be RECOGNIZE, SUSPEND, or DISSOLVE.",
        )

    org = repository.fetch_organization_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    status_map = {"RECOGNIZE": "RECOGNIZED", "SUSPEND": "SUSPENDED", "DISSOLVE": "DISSOLVED"}
    org.status          = status_map[data.decision]
    org.secretary_notes = data.secretary_notes
    org.processed_by    = secretary_id
    org.processed_at    = datetime.now(timezone.utc)

    db.commit()
    db.refresh(org)

    audit_service.log_event(
        database_session=db,
        event_type="ORG_STATUS_UPDATED",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="student_organization",
        target_id=org_id,
        ip_address=ip_address,
        payload={"decision": data.decision, "new_status": org.status, "org_name": org.org_name},
    )
    return org


def get_organization(db: Session, org_id: int) -> models.StudentOrganization:
    org = repository.fetch_organization_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org


def add_facility(db: Session, data: schemas.FacilityCreate) -> models.Facility:
    if data.facility_type not in _VALID_FACILITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid facility_type. Must be one of: {', '.join(sorted(_VALID_FACILITY_TYPES))}.",
        )

    existing = repository.fetch_facility_by_code(db, data.facility_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A facility with code '{data.facility_code}' already exists.",
        )

    facility = models.Facility(
        facility_code=data.facility_code,
        facility_name=data.facility_name,
        facility_type=data.facility_type,
        building=data.building,
        capacity=data.capacity,
        description=data.description,
    )
    return repository.save_facility(db, facility)


def update_facility(db: Session, facility_id: int, data: schemas.FacilityUpdate) -> models.Facility:
    facility = repository.fetch_facility_by_id(db, facility_id)
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found.")

    update_dict = data.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        setattr(facility, key, value)

    db.commit()
    db.refresh(facility)
    return facility


def submit_booking_request(
    db: Session,
    requestor_id: int,
    data: schemas.FacilityBookingCreate,
    ip_address: Optional[str] = None,
) -> models.FacilityBooking:
    facility = repository.fetch_facility_by_id(db, data.facility_id)
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found.")
    if not facility.is_bookable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{facility.facility_name}' is not currently available for booking.",
        )
    if data.time_end <= data.time_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="time_end must be after time_start.",
        )
    if data.org_id:
        org = repository.fetch_organization_by_id(db, data.org_id)
        if not org or org.status != "RECOGNIZED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The specified organization is not recognized.",
            )

    conflicts = repository.fetch_conflicting_bookings(db, data.facility_id, data.time_start, data.time_end)
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Time slot conflict: '{facility.facility_name}' already has an approved "
                f"booking from {conflicts[0].time_start.strftime('%H:%M')} to "
                f"{conflicts[0].time_end.strftime('%H:%M')} on {conflicts[0].booking_date}."
            ),
        )

    booking = models.FacilityBooking(
        facility_id=data.facility_id,
        requestor_account_id=requestor_id,
        org_id=data.org_id,
        event_title=data.event_title,
        event_description=data.event_description,
        booking_date=data.booking_date,
        time_start=data.time_start,
        time_end=data.time_end,
        attendee_count=data.attendee_count,
        status="PENDING",
    )
    saved = repository.save_booking(db, booking)

    audit_service.log_event(
        database_session=db,
        event_type="FACILITY_BOOKING_SUBMITTED",
        actor_id=requestor_id,
        target_type="facility_booking",
        target_id=saved.id,
        ip_address=ip_address,
        payload={
            "facility_id":   data.facility_id,
            "facility_name": facility.facility_name,
            "booking_date":  str(data.booking_date),
            "event_title":   data.event_title,
        },
    )
    return saved


def process_booking(
    db: Session,
    booking_id: int,
    data: schemas.BookingProcessDecision,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.FacilityBooking:
    if data.decision not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be APPROVE or REJECT.")

    booking = repository.fetch_booking_by_id(db, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    if booking.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PENDING bookings can be processed (current: {booking.status}).",
        )

    now = datetime.now(timezone.utc)

    if data.decision == "APPROVE":
        conflicts = repository.fetch_conflicting_bookings(
            db, booking.facility_id, booking.time_start, booking.time_end, exclude_booking_id=booking_id
        )
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve: a conflicting booking (ID: {conflicts[0].id}) was approved in the same time slot.",
            )
        booking.status = "APPROVED"
    else:
        if not data.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="rejection_reason is required when rejecting a booking.",
            )
        booking.status           = "REJECTED"
        booking.rejection_reason = data.rejection_reason

    if data.secretary_notes:
        booking.secretary_notes = data.secretary_notes
    booking.processed_by_secretary_id = secretary_id
    booking.processed_at               = now

    db.commit()
    db.refresh(booking)

    audit_service.log_event(
        database_session=db,
        event_type="FACILITY_BOOKING_PROCESSED",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="facility_booking",
        target_id=booking_id,
        ip_address=ip_address,
        payload={"decision": data.decision, "facility_id": booking.facility_id},
    )
    return booking


def cancel_booking(
    db: Session,
    booking_id: int,
    requestor_id: int,
    ip_address: Optional[str] = None,
) -> models.FacilityBooking:
    booking = repository.fetch_booking_by_id(db, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    if booking.requestor_account_id != requestor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only cancel your own bookings.")
    if booking.status in ("REJECTED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking is already in a terminal state ({booking.status}).",
        )

    booking.status       = "CANCELLED"
    booking.cancelled_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(booking)

    audit_service.log_event(
        database_session=db,
        event_type="FACILITY_BOOKING_CANCELLED",
        actor_id=requestor_id,
        target_type="facility_booking",
        target_id=booking_id,
        ip_address=ip_address,
        payload={"facility_id": booking.facility_id},
    )
    return booking


def get_booking(db: Session, booking_id: int) -> models.FacilityBooking:
    booking = repository.fetch_booking_by_id(db, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return booking
