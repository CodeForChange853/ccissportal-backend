# backend-v2/src/modules/audit/models.py

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Index
from sqlalchemy.sql import func
from src.core.database_setup import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id    = Column(Integer, primary_key=True, index=True)

    # WHO
    actor_id    = Column(Integer, nullable=True, index=True)
    actor_email = Column(String(255), nullable=True)

    # WHAT
    event_type  = Column(String(64),  nullable=False)

    # TARGET
    target_type = Column(String(64),  nullable=True)
    target_id   = Column(String(64),  nullable=True)

    # CONTEXT
    ip_address  = Column(String(45),  nullable=True)
    payload     = Column(JSON,        nullable=True)

    # AI ANOMALY
    anomaly_score = Column(Float, default=0.0)

    # SE-08 — AI narrative fields (added via ALTER TABLE IF NOT EXISTS on startup)
    anomaly_narrative            = Column(Text,         nullable=True)
    narrative_status             = Column(String(20),   nullable=False, default='NONE', server_default='NONE')
    narrative_acknowledged_at    = Column(DateTime(timezone=True), nullable=True)

    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Most common query: filter by event_type, order by created_at DESC
        Index("ix_audit_event_type_created", "event_type", "created_at"),
        # Actor-specific lookups (admin investigation, tripwire checks)
        Index("ix_audit_actor_email_created", "actor_email", "created_at"),
        # Narrative processing job: fetch by narrative_status
        Index("ix_audit_narrative_status", "narrative_status"),
    )