# backend-v2/src/modules/faculty/schemas.py

from pydantic import BaseModel
from typing import Optional, List


class GradeSubmissionRequest(BaseModel):
    student_account_id: int
    curriculum_subject_id: Optional[int] = None 
    subject_code: Optional[str] = None
    midterm_grade: Optional[float] = None
    system_grade: Optional[float] = None
    final_grade: Optional[float] = None
    override_reason: Optional[str] = None
    completion_status: Optional[str] = None
    client_updated_at: Optional[int] = None

class SyncGradesRequest(BaseModel):
    updates: List[GradeSubmissionRequest]

class SyncGradesResponse(BaseModel):
    synced_count: int = 0
    skipped_count: int = 0
    skipped_keys: List[str] = []

class ClassRosterResponse(BaseModel):
    student_id: str
    student_name: str
    system_grade: Optional[float]
    final_grade: Optional[float]
    override_reason: Optional[str]
    status: str


class StudentGradeReport(BaseModel):
    subject_code:      str
    subject_title:     str
    credit_units:      int
    midterm_grade:     Optional[float]
    final_grade:       Optional[float]
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
    schedule: Optional[str] = "TBA"
    room: Optional[str] = "TBA"
    section: Optional[str] = "Regular"


class AdminFacultyListItem(BaseModel):
    account_id:             int
    email_address:          str
    first_name:             str
    last_name:              str
    employee_id:            Optional[str] = None
    academic_department:    str
    current_teaching_load:  int
    maximum_teaching_load:  int
    is_available_for_classes: bool

    class Config:
        from_attributes = True


# ── Triage Alerts 

class TriageAlertOut(BaseModel):
    alert_type: str            
    severity: str              
    title: str
    description: str
    subject_code: Optional[str] = None
    student_name: Optional[str] = None
    ticket_id: Optional[int] = None


# ── Consultations 

class ConsultationSlotCreate(BaseModel):
    available_date: str
    start_time: str
    end_time: str

class ConsultationSlotUpdate(BaseModel):
    available_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_active: Optional[bool] = None

class ConsultationSlotOut(BaseModel):
    slot_id: int
    available_date: str
    start_time: str
    end_time: str
    is_active: bool

    class Config:
        from_attributes = True

class ConsultationRequestOut(BaseModel):
    request_id: int
    student_name: Optional[str] = None
    faculty_name: Optional[str] = None
    reason: str
    booking_date: str
    start_time: str
    end_time: str
    status: str
    created_at: Optional[str] = None

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
    booking_date: str
    start_time: str
    end_time: str
    reason: str