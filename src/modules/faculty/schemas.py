# backend-v2/src/modules/faculty/schemas.py

from pydantic import BaseModel
from typing import Optional, List


class GradeSubmissionRequest(BaseModel):
    student_account_id: int
    curriculum_subject_id: Optional[int] = None # Or subject_code via sync
    subject_code: Optional[str] = None
    midterm_grade: Optional[float] = None
    system_grade: Optional[float] = None
    final_grade: Optional[float] = None
    override_reason: Optional[str] = None
    completion_status: Optional[str] = None
    # Epoch-ms timestamp from the client device for last-write-wins conflict resolution
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