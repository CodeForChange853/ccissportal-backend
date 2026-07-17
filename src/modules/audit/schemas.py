# backend-v2/src/modules/audit/schemas.py

from pydantic import BaseModel, ConfigDict
from typing import Any
from datetime import datetime


class AuditEventOut(BaseModel):
    event_id:      int
    actor_email:   str | None
    event_type:    str
    target_type:   str | None
    target_id:     str | None
    ip_address:    str | None
    payload:       Any | None
    anomaly_score: float
    created_at:    datetime

    # SE-08 narrative fields
    anomaly_narrative:         str | None      = None
    narrative_status:          str | None      = None
    narrative_acknowledged_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditSummaryOut(BaseModel):
    total_events:    int
    high_anomalies:  int
    anomaly_score:   float          
    top_anomalies:   list[AuditEventOut]


class AuditLogRequest(BaseModel):
    actor_id:    int | None   = None
    actor_email: str | None   = None
    event_type:  str
    target_type: str | None   = None
    target_id:   str | None   = None
    ip_address:  str | None   = None
    payload:     Any | None   = None


class NarrativeRunResponse(BaseModel):
    generated: int
    failed:    int
    skipped:   int