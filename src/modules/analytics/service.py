"""
SE-01: Predictive Enrollment Demand Analytics

Two-tier forecasting strategy:
  - 1 historical data point  → SINGLE_POINT_HEURISTIC  (±20% margin)
  - 2+ historical data points → LINEAR_REGRESSION       (±90% CI from residual std)
  - 0 data points             → NO_DATA_BASELINE        (returns 0)

Demand is aggregated per (subject_code, target_year_level, target_semester, year)
using StudentEnrollmentRequest.extracted_subjects (list[str] of subject codes).
GradebookEntry counts supplement the history when no request data exists.
"""

import math
from collections import defaultdict
from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from . import repository
from .models import EnrollmentForecast, ForecastAlert

# Assumed students per section for capacity calculations.
ASSUMED_SECTION_SIZE = 40


# ── Demand aggregation ─────────────────────────────────────────────────────────

def _build_demand_history(
    requests,
) -> dict[tuple[str, int, int], dict[int, int]]:
    """
    Returns {(subject_code, year_level, semester): {calendar_year: request_count}}.
    Each entry in extracted_subjects (a list of subject codes) counts as +1 demand
    for that subject in the year the request was submitted.
    """
    history: dict[tuple[str, int, int], dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for req in requests:
        if not req.extracted_subjects:
            continue
        cal_year = req.date_submitted.year if req.date_submitted else datetime.now().year
        for code in req.extracted_subjects:
            key = (code, req.target_year_level, req.target_semester)
            history[key][cal_year] += 1
    return history


# ── Linear regression forecast ────────────────────────────────────────────────

def _forecast(year_counts: dict[int, int]) -> tuple[int, int, int]:
    """
    Returns (predicted, lower_bound, upper_bound) for the year after the last
    data point, using a simple OLS linear regression over time.
    """
    if not year_counts:
        return 0, 0, 0

    sorted_pairs = sorted(year_counts.items())

    if len(sorted_pairs) == 1:
        base = sorted_pairs[0][1]
        margin = max(2, int(base * 0.20))
        return base, max(0, base - margin), base + margin

    years  = np.array([p[0] for p in sorted_pairs], dtype=float)
    counts = np.array([p[1] for p in sorted_pairs], dtype=float)

    mean_y = years.mean()
    mean_c = counts.mean()
    denom  = ((years - mean_y) ** 2).sum()
    slope  = ((years - mean_y) * (counts - mean_c)).sum() / denom if denom else 0.0
    intercept = mean_c - slope * mean_y

    next_year = float(years[-1] + 1)
    predicted = max(0.0, slope * next_year + intercept)

    # 90% CI margin from residual standard deviation
    residuals = counts - (slope * years + intercept)
    std       = residuals.std() if len(residuals) > 2 else mean_c * 0.15
    margin    = int(round(1.64 * std))

    return (
        int(round(predicted)),
        max(0, int(round(predicted - margin))),
        int(round(predicted + margin)),
    )


def _model_type(n_points: int) -> str:
    if n_points == 0:
        return "NO_DATA_BASELINE"
    if n_points == 1:
        return "SINGLE_POINT_HEURISTIC"
    return "LINEAR_REGRESSION"


# ── Alert generation (SE-01.04) ───────────────────────────────────────────────

def _generate_alerts(db: Session, forecasts: list[EnrollmentForecast]) -> int:
    """
    Clears undismissed alerts and regenerates them from the latest forecasts.
    Returns the count of new alerts created.
    """
    repository.clear_active_alerts(db)

    _, remaining_capacity = repository.fetch_faculty_capacity(db)
    total_sections_needed = sum(
        math.ceil(f.predicted_demand / ASSUMED_SECTION_SIZE)
        for f in forecasts
        if f.predicted_demand > 0
    )

    alerts: list[ForecastAlert] = []

    # System-level: total sections needed exceeds total available faculty load
    if total_sections_needed > 0 and total_sections_needed > remaining_capacity:
        alerts.append(ForecastAlert(
            alert_type="CAPACITY_EXCEEDED",
            subject_code=None,
            subject_title=None,
            message=(
                f"Forecast projects ~{total_sections_needed} section(s) needed across all subjects, "
                f"but only {remaining_capacity} faculty teaching slot(s) remain available. "
                f"Consider adding faculty or increasing teaching loads before the next enrollment period."
            ),
            predicted_demand=total_sections_needed,
            available_capacity=remaining_capacity,
        ))

    # Per-subject: demand grew more than 25% from the most recent known data point
    for f in forecasts:
        if not f.historical_data or len(f.historical_data) < 2:
            continue
        sorted_history = sorted(f.historical_data, key=lambda x: x["year"])
        last_count = sorted_history[-1]["count"]
        if last_count > 0 and f.predicted_demand > last_count * 1.25:
            growth_pct = int(((f.predicted_demand - last_count) / last_count) * 100)
            alerts.append(ForecastAlert(
                alert_type="DEMAND_SURGE",
                subject_code=f.subject_code,
                subject_title=f.subject_title,
                message=(
                    f"{f.subject_code} ({f.subject_title}) is projected to see a "
                    f"{growth_pct}% demand increase "
                    f"({last_count} → {f.predicted_demand} students). "
                    f"Proactive section creation is recommended."
                ),
                predicted_demand=f.predicted_demand,
                available_capacity=None,
            ))

    for alert in alerts:
        repository.save_alert(db, alert)

    return len(alerts)


# ── Public entry point (SE-01.02 + SE-01.05) ─────────────────────────────────

def run_forecast(db: Session) -> dict:
    """
    Aggregates historical enrollment demand and fits per-subject forecasts.
    Saves results to enrollment_forecasts, regenerates forecast_alerts.
    Called manually via POST /analytics/admin/run-forecast and automatically
    by APScheduler on the 1st of each month (SE-01.05).
    """
    requests = repository.fetch_enrollment_requests_with_subjects(db)
    subjects = repository.fetch_all_curriculum_subjects(db)

    if not subjects:
        return {"status": "SKIPPED", "reason": "No curriculum subjects found.", "forecasts_generated": 0, "data_points_used": 0}

    demand_history  = _build_demand_history(requests)
    gradebook_counts = repository.fetch_gradebook_counts_per_subject(db)
    current_year    = datetime.now().year

    forecasts: list[EnrollmentForecast] = []

    for subj in subjects:
        key         = (subj.subject_code, subj.target_year_level, subj.target_semester)
        year_counts = dict(demand_history.get(key, {}))

        # Supplement with GradebookEntry counts when no request history exists
        gb_count = gradebook_counts.get(subj.subject_id, 0)
        if gb_count > 0 and (current_year - 1) not in year_counts:
            year_counts[current_year - 1] = gb_count

        predicted, lower, upper = _forecast(year_counts)
        next_year = max(year_counts.keys()) + 1 if year_counts else current_year + 1

        forecasts.append(EnrollmentForecast(
            subject_code=           subj.subject_code,
            subject_title=          subj.subject_title,
            target_year_level=      subj.target_year_level,
            target_semester=        subj.target_semester,
            forecast_academic_year= str(next_year),
            predicted_demand=       predicted,
            lower_bound=            lower,
            upper_bound=            upper,
            historical_data=[
                {"year": yr, "count": cnt}
                for yr, cnt in sorted(year_counts.items())
            ],
            model_type=     _model_type(len(year_counts)),
            confidence_level=0.90,
            is_current=     True,
        ))

    repository.save_forecasts(db, forecasts)
    alerts_count = _generate_alerts(db, forecasts)

    return {
        "status":              "SUCCESS",
        "forecasts_generated": len(forecasts),
        "data_points_used":    len(requests),
        "alerts_generated":    alerts_count,
    }
