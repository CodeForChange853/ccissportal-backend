from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


class CORReleaseAction(BaseModel):
    secretary_notes: str | None = Field(None, max_length=500)


class CORQueueItem(BaseModel):
    request_id:                   int
    student_account_id:           int
    student_name:                 str | None      = None
    student_number:               str | None      = None
    target_year_level:            int
    target_semester:              int
    extracted_subjects:           Any | None      = None
    review_status:                str
    cor_release_status:           str
    cor_released_at:              datetime | None = None
    cor_released_by_secretary_id: int | None      = None
    date_submitted:               datetime | None = None
