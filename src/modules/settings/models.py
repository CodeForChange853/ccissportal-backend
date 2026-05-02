# backend-v2/src/modules/settings/models.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from src.core.database_setup import Base


class SystemSettings(Base):

    __tablename__ = "system_settings"

    settings_id = Column(Integer, primary_key=True, default=1)

    #  Enrollment Gate 
    is_enrollment_open = Column(Boolean, nullable=False, default=False)

    #  Faculty Load Balancer 
    global_max_teaching_load = Column(Integer, nullable=False, default=4)

    #  Student Registration Security 

    student_registration_passkey = Column(String(100), nullable=False, default="CCIS2025")

    #  Audit 
    last_updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )