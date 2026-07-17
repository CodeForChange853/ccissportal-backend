from pydantic import BaseModel, ConfigDict
from datetime import datetime


class HistoricalDataPoint(BaseModel):
    year: int
    count: int


class SubjectForecastResponse(BaseModel):
    forecast_id:            int
    subject_code:           str
    subject_title:          str
    target_year_level:      int
    target_semester:        int
    forecast_academic_year: str
    predicted_demand:       int
    lower_bound:            int
    upper_bound:            int
    historical_data:        list[HistoricalDataPoint]
    model_type:             str
    confidence_level:       float
    generated_at:           datetime

    model_config = ConfigDict(from_attributes=True)


class ForecastAlertResponse(BaseModel):
    alert_id:           int
    alert_type:         str
    subject_code:       str | None = None
    subject_title:      str | None = None
    message:            str
    predicted_demand:   int | None = None
    available_capacity: int | None = None
    created_at:         datetime

    model_config = ConfigDict(from_attributes=True)


class ForecastRunResponse(BaseModel):
    status:              str
    forecasts_generated: int
    data_points_used:    int
    alerts_generated:    int


class ForecastSummaryResponse(BaseModel):
    total_subjects:           int
    total_predicted_demand:   int
    total_sections_needed:    int
    available_faculty_capacity: int
    active_alerts:            int
    last_updated:             datetime | None = None
    forecasts:                list[SubjectForecastResponse]
