from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Text
from sqlalchemy.sql import func
from src.core.database_setup import Base


class EnrollmentForecast(Base):
    __tablename__ = "enrollment_forecasts"

    forecast_id            = Column(Integer, primary_key=True, index=True)
    subject_code           = Column(String(50),  index=True, nullable=False)
    subject_title          = Column(String(255), nullable=False)
    target_year_level      = Column(Integer, nullable=False)
    target_semester        = Column(Integer, nullable=False)
    forecast_academic_year = Column(String(20),  nullable=False)
    predicted_demand       = Column(Integer, nullable=False, default=0)
    lower_bound            = Column(Integer, nullable=False, default=0)
    upper_bound            = Column(Integer, nullable=False, default=0)
    # [{year: int, count: int}, ...]
    historical_data        = Column(JSON, nullable=True)
    model_type             = Column(String(50), default="LINEAR_REGRESSION")
    confidence_level       = Column(Float, default=0.90)
    generated_at           = Column(DateTime(timezone=True), server_default=func.now())
    is_current             = Column(Boolean, default=True, index=True)


class ForecastAlert(Base):
    __tablename__ = "forecast_alerts"

    alert_id           = Column(Integer, primary_key=True, index=True)
    # CAPACITY_EXCEEDED | DEMAND_SURGE
    alert_type         = Column(String(50), nullable=False, index=True)
    subject_code       = Column(String(50),  nullable=True)
    subject_title      = Column(String(255), nullable=True)
    message            = Column(Text, nullable=False)
    predicted_demand   = Column(Integer, nullable=True)
    available_capacity = Column(Integer, nullable=True)
    is_dismissed       = Column(Boolean, default=False, index=True)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    dismissed_at       = Column(DateTime(timezone=True), nullable=True)
