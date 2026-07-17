import math

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.security import require_admin
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

analytics_router = APIRouter(
    prefix="/analytics",
    tags=["Enrollment Analytics"],
)


# SE-01.03 — Forecast visualisation data for the admin dashboard
@analytics_router.get(
    "/admin/enrollment-forecast",
    response_model=schemas.ForecastSummaryResponse,
)
def get_enrollment_forecast(
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    forecasts = repository.fetch_current_forecasts(database_session)
    alerts    = repository.fetch_active_alerts(database_session)
    _, remaining_capacity = repository.fetch_faculty_capacity(database_session)

    total_predicted = sum(f.predicted_demand for f in forecasts)
    total_sections  = sum(
        math.ceil(f.predicted_demand / service.ASSUMED_SECTION_SIZE)
        for f in forecasts
        if f.predicted_demand > 0
    )
    last_updated = max((f.generated_at for f in forecasts), default=None)

    forecast_responses = [
        schemas.SubjectForecastResponse(
            forecast_id=            f.forecast_id,
            subject_code=           f.subject_code,
            subject_title=          f.subject_title,
            target_year_level=      f.target_year_level,
            target_semester=        f.target_semester,
            forecast_academic_year= f.forecast_academic_year,
            predicted_demand=       f.predicted_demand,
            lower_bound=            f.lower_bound,
            upper_bound=            f.upper_bound,
            historical_data=        f.historical_data or [],
            model_type=             f.model_type,
            confidence_level=       f.confidence_level,
            generated_at=           f.generated_at,
        )
        for f in forecasts
    ]

    return schemas.ForecastSummaryResponse(
        total_subjects=             len(forecasts),
        total_predicted_demand=     total_predicted,
        total_sections_needed=      total_sections,
        available_faculty_capacity= remaining_capacity,
        active_alerts=              len(alerts),
        last_updated=               last_updated,
        forecasts=                  forecast_responses,
    )


# SE-01.02 / SE-01.05 — Manual retrain trigger
@analytics_router.post(
    "/admin/run-forecast",
    response_model=schemas.ForecastRunResponse,
)
def trigger_forecast_run(
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    result = service.run_forecast(database_session)
    return schemas.ForecastRunResponse(
        status=              result.get("status", "UNKNOWN"),
        forecasts_generated= result.get("forecasts_generated", 0),
        data_points_used=    result.get("data_points_used", 0),
        alerts_generated=    result.get("alerts_generated", 0),
    )


# SE-01.04 — Active capacity / surge alerts
@analytics_router.get(
    "/admin/demand-alerts",
    response_model=list[schemas.ForecastAlertResponse],
)
def get_demand_alerts(
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    return repository.fetch_active_alerts(database_session)


@analytics_router.post(
    "/admin/apply-tables",
    status_code=status.HTTP_200_OK,
)
def apply_analytics_tables(
    _admin: UserAccount = Depends(require_admin),
):
    """Creates enrollment_forecasts and forecast_alerts tables if they don't exist. Safe to call repeatedly."""
    try:
        from src.core.database_setup import Base, database_engine
        from src.modules.analytics.models import EnrollmentForecast, ForecastAlert
        Base.metadata.create_all(
            bind=database_engine,
            tables=[EnrollmentForecast.__table__, ForecastAlert.__table__],
            checkfirst=True,
        )
        return {"status": "SUCCESS", "message": "Analytics tables created/verified successfully."}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Table creation failed: {exc}",
        )


@analytics_router.post(
    "/admin/demand-alerts/{alert_id}/dismiss",
    status_code=status.HTTP_200_OK,
)
def dismiss_demand_alert(
    alert_id: int,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    alert = repository.fetch_alert_by_id(database_session, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert #{alert_id} not found.",
        )
    repository.dismiss_alert(database_session, alert)
    return {"message": f"Alert #{alert_id} dismissed."}
