from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_admin_or_secretary
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

facilities_router = APIRouter(prefix="/secretariat", tags=["Secretariat — Organizations & Facilities"])


# ── Student Organizations ─────────────────────────────────────────────────────

@facilities_router.post("/orgs", response_model=schemas.StudentOrganizationResponse, status_code=status.HTTP_201_CREATED)
def register_organization(
    request: Request,
    data: schemas.StudentOrganizationCreate,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.register_organization(
        db=db,
        requestor_id=current_user.account_id,
        data=data,
        ip_address=request.client.host if request.client else None,
    )


@facilities_router.get("/orgs", response_model=List[schemas.StudentOrganizationResponse])
def list_organizations(
    status_filter: str = Query(default="ALL"),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(get_current_user),
):
    resolved = None if status_filter == "ALL" else status_filter
    return repository.fetch_organizations(db, status_filter=resolved)


@facilities_router.get("/orgs/{org_id}", response_model=schemas.StudentOrganizationResponse)
def get_organization(
    org_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(get_current_user),
):
    return service.get_organization(db, org_id)


@facilities_router.patch("/orgs/{org_id}/process", response_model=schemas.StudentOrganizationResponse)
def process_org_registration(
    org_id: int,
    request: Request,
    data: schemas.OrgProcessDecision,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.process_org_registration(
        db=db,
        org_id=org_id,
        data=data,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


# ── Facilities ────────────────────────────────────────────────────────────────

@facilities_router.post("/facilities", response_model=schemas.FacilityResponse, status_code=status.HTTP_201_CREATED)
def create_facility(
    data: schemas.FacilityCreate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.add_facility(db=db, data=data)


@facilities_router.get("/facilities", response_model=List[schemas.FacilityResponse])
def list_facilities(
    bookable_only: bool = Query(default=False),
    facility_type: str = Query(default=None),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(get_current_user),
):
    return repository.fetch_facilities(db, bookable_only=bookable_only, facility_type=facility_type)


@facilities_router.patch("/facilities/{facility_id}", response_model=schemas.FacilityResponse)
def update_facility(
    facility_id: int,
    data: schemas.FacilityUpdate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.update_facility(db=db, facility_id=facility_id, data=data)


# ── Bookings ──────────────────────────────────────────────────────────────────

@facilities_router.post("/bookings", response_model=schemas.FacilityBookingResponse, status_code=status.HTTP_201_CREATED)
def submit_booking_request(
    request: Request,
    data: schemas.FacilityBookingCreate,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.submit_booking_request(
        db=db,
        requestor_id=current_user.account_id,
        data=data,
        ip_address=request.client.host if request.client else None,
    )


@facilities_router.get("/bookings/my", response_model=List[schemas.FacilityBookingResponse])
def get_my_bookings(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return repository.fetch_bookings(db, requestor_account_id=current_user.account_id)


@facilities_router.get("/bookings", response_model=List[schemas.FacilityBookingResponse])
def list_bookings(
    status_filter: str = Query(default="ALL"),
    facility_id: int = Query(default=None),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    resolved = None if status_filter == "ALL" else status_filter
    return repository.fetch_bookings(db, status_filter=resolved, facility_id=facility_id)


@facilities_router.get("/bookings/facility/{facility_id}", response_model=List[schemas.FacilityBookingResponse])
def list_facility_bookings(
    facility_id: int,
    status_filter: str = Query(default="APPROVED"),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(get_current_user),
):
    resolved = None if status_filter == "ALL" else status_filter
    return repository.fetch_bookings(db, facility_id=facility_id, status_filter=resolved)


@facilities_router.get("/bookings/{booking_id}", response_model=schemas.FacilityBookingResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(get_current_user),
):
    return service.get_booking(db, booking_id)


@facilities_router.patch("/bookings/{booking_id}/process", response_model=schemas.FacilityBookingResponse)
def process_booking(
    booking_id: int,
    request: Request,
    data: schemas.BookingProcessDecision,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.process_booking(
        db=db,
        booking_id=booking_id,
        data=data,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@facilities_router.patch("/bookings/{booking_id}/cancel", response_model=schemas.FacilityBookingResponse)
def cancel_booking(
    booking_id: int,
    request: Request,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.cancel_booking(
        db=db,
        booking_id=booking_id,
        requestor_id=current_user.account_id,
        ip_address=request.client.host if request.client else None,
    )
