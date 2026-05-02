# backend-v2/src/modules/audit/schemas.py

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class AuditEventOut(BaseModel):
    event_id:      int
    actor_email:   Optional[str]
    event_type:    str
    target_type:   Optional[str]
    target_id:     Optional[str]
    ip_address:    Optional[str]
    payload:       Optional[Any]
    anomaly_score: float
    created_at:    datetime

    class Config:
        from_attributes = True


class AuditSummaryOut(BaseModel):
    total_events:    int
    high_anomalies:  int
    anomaly_score:   float          
    top_anomalies:   list[AuditEventOut]


class AuditLogRequest(BaseModel):
    actor_id:    Optional[int]   = None
    actor_email: Optional[str]   = None
    event_type:  str
    target_type: Optional[str]   = None
    target_id:   Optional[str]   = None
    ip_address:  Optional[str]   = None
    payload:     Optional[Any]   = None