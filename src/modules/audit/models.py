# backend-v2/src/modules/audit/models.py

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON
from sqlalchemy.sql import func
from src.core.database_setup import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id    = Column(Integer, primary_key=True, index=True)

    # WHO
    actor_id    = Column(Integer, nullable=True, index=True)
    actor_email = Column(String(255), nullable=True, index=True)

    # WHAT
    event_type  = Column(String(64),  nullable=False, index=True)


    # TARGET
    target_type = Column(String(64),  nullable=True) 
    target_id   = Column(String(64),  nullable=True)

    # CONTEXT
    ip_address  = Column(String(45),  nullable=True)
    payload     = Column(JSON,        nullable=True)   

    # AI ANOMALY
    anomaly_score = Column(Float, default=0.0)        

    created_at  = Column(DateTime(timezone=True), server_default=func.now(), index=True)