# backend-v2/src/modules/faculty/schemas.py

from pydantic import BaseModel, ConfigDict, Field
from typing import List


class GradeSubmissionRequest(BaseModel):
    student_account_id: int
    curriculum_subject_id: int | None = None 
    subject_code: str | None = Field(None, max_length=50)
    midterm_grade: float | None = None
    system_grade: float | None = None
    final_grade: float | None = None
    raw_scores: dict | None = None
    override_reason: str | None = Field(None, max_length=500)
    completion_status: str | None = Field(None, max_length=50)
    client_updated_at: int | None = None

class SyncGradesRequest(BaseModel):
    updates: List[GradeSubmissionRequest]

class SyncGradesResponse(BaseModel):
    synced_count: int = 0
    skipped_count: int = 0
    skipped_keys: List[str] = []

class ClassRosterResponse(BaseModel):
    student_account_id: int
    curriculum_subject_id: int  # Added to ensure sync matches
    student_id: str
    student_name: str
    midterm_grade: float | None
    system_grade: float | None
    final_grade: float | None
    override_reason: str | None
    status: str


class StudentGradeReport(BaseModel):
    subject_code:      str
    subject_title:     str
    credit_units:      int
    target_year_level: int
    target_semester:   int
    midterm_grade:     float | None
    system_grade:      float | None
    final_grade:       float | None
    completion_status: str


class FacultyAssignmentRequest(BaseModel):
    faculty_account_id: int
    curriculum_subject_id: int


class BulkFacultyAssignmentRequest(BaseModel):
    
    faculty_account_id: int
    curriculum_subject_ids: List[int]


class FacultySubjectLoad(BaseModel):
    code: str
    title: str
    units: int
    schedule: str | None = "TBA"
    room: str | None = "TBA"
    section: str | None = "Regular"


class AdminFacultyListItem(BaseModel):
    account_id:             int
    email_address:          str
    first_name:             str
    last_name:              str
    employee_id:            str | None = None
    academic_department:    str
    current_teaching_load:  int
    maximum_teaching_load:  int
    is_available_for_classes: bool
    specialization_tags:    str | None = None
    performance_score:      float | None = None

    model_config = ConfigDict(from_attributes=True)


# SE-02 — Intelligent Faculty Matching

class SpecializationUpdateRequest(BaseModel):
    specialization_tags: str  # JSON array string e.g. '["algorithms","networking"]'


class ScoreBreakdown(BaseModel):
    specialization: int
    performance:    int
    load:           int
    availability:   int


class FacultySuitabilityItem(BaseModel):
    account_id:           int
    email_address:        str
    first_name:           str
    last_name:            str
    academic_department:  str
    current_teaching_load: int
    maximum_teaching_load: int
    specialization_tags:  str | None = None
    suitability_score:    int
    breakdown:            ScoreBreakdown
    is_top_pick:          bool


class FacultyMatchResponse(BaseModel):
    subject_id:    int
    subject_code:  str
    subject_title: str
    candidates:    List[FacultySuitabilityItem]


# ── Triage Alerts 

class TriageAlertOut(BaseModel):
    alert_type: str            
    severity: str              
    title: str
    description: str
    subject_code: str | None = None
    student_name: str | None = None
    ticket_id: int | None = None


# ── Consultations 

class ConsultationSlotCreate(BaseModel):
    available_date: str
    start_time: str
    end_time: str

class ConsultationSlotUpdate(BaseModel):
    available_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    is_active: bool | None = None

class ConsultationSlotOut(BaseModel):
    slot_id: int
    available_date: str
    start_time: str
    end_time: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ConsultationRequestOut(BaseModel):
    request_id: int
    student_name: str | None = None
    faculty_name: str | None = None
    reason: str
    booking_date: str
    start_time: str
    end_time: str
    status: str
    created_at: str | None = None

class ConsultationStatusUpdate(BaseModel):
    status: str   

class AvailableTimeChunk(BaseModel):
    start_time: str
    end_time: str

class FacultyWithSlotsOut(BaseModel):
    account_id: int
    faculty_name: str
    academic_department: str

class StudentConsultationBookingCreate(BaseModel):
    faculty_account_id: int
    booking_date: str = Field(..., max_length=50)
    start_time: str = Field(..., max_length=20)
    end_time: str = Field(..., max_length=20)
    reason: str = Field(..., max_length=500)