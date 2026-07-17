from datetime import datetime
from sqlalchemy.orm import Session
from . import models


def save_organization(db: Session, org: models.StudentOrganization) -> models.StudentOrganization:
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def fetch_organization_by_id(db: Session, org_id: int) -> models.StudentOrganization | None:
    return db.query(models.StudentOrganization).filter(models.StudentOrganization.id == org_id).first()


def fetch_organization_by_name(db: Session, org_name: str) -> models.StudentOrganization | None:
    return db.query(models.StudentOrganization).filter(models.StudentOrganization.org_name == org_name).first()


def fetch_organizations(db: Session, status_filter: str | None = None) -> list[models.StudentOrganization]:
    query = db.query(models.StudentOrganization)
    if status_filter:
        query = query.filter(models.StudentOrganization.status == status_filter)
    return query.order_by(models.StudentOrganization.org_name.asc()).all()


def save_facility(db: Session, facility: models.Facility) -> models.Facility:
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


def fetch_facility_by_id(db: Session, facility_id: int) -> models.Facility | None:
    return db.query(models.Facility).filter(models.Facility.id == facility_id).first()


def fetch_facility_by_code(db: Session, facility_code: str) -> models.Facility | None:
    return db.query(models.Facility).filter(models.Facility.facility_code == facility_code).first()


def fetch_facilities(
    db: Session,
    bookable_only: bool = False,
    facility_type: str | None = None,
) -> list[models.Facility]:
    query = db.query(models.Facility)
    if bookable_only:
        query = query.filter(models.Facility.is_bookable == True)
    if facility_type:
        query = query.filter(models.Facility.facility_type == facility_type)
    return query.order_by(models.Facility.facility_name.asc()).all()


def save_booking(db: Session, booking: models.FacilityBooking) -> models.FacilityBooking:
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def fetch_booking_by_id(db: Session, booking_id: int) -> models.FacilityBooking | None:
    return db.query(models.FacilityBooking).filter(models.FacilityBooking.id == booking_id).first()


def fetch_bookings(
    db: Session,
    status_filter: str | None = None,
    facility_id: int | None = None,
    requestor_account_id: int | None = None,
) -> list[models.FacilityBooking]:
    query = db.query(models.FacilityBooking)
    if status_filter:
        query = query.filter(models.FacilityBooking.status == status_filter)
    if facility_id:
        query = query.filter(models.FacilityBooking.facility_id == facility_id)
    if requestor_account_id:
        query = query.filter(models.FacilityBooking.requestor_account_id == requestor_account_id)
    return query.order_by(models.FacilityBooking.time_start.asc()).all()


def fetch_conflicting_bookings(
    db: Session,
    facility_id: int,
    time_start: datetime,
    time_end: datetime,
    exclude_booking_id: int | None = None,
) -> list[models.FacilityBooking]:
    query = db.query(models.FacilityBooking).filter(
        models.FacilityBooking.facility_id == facility_id,
        models.FacilityBooking.status == "APPROVED",
        models.FacilityBooking.time_start < time_end,
        models.FacilityBooking.time_end > time_start,
    )
    if exclude_booking_id:
        query = query.filter(models.FacilityBooking.id != exclude_booking_id)
    return query.all()
