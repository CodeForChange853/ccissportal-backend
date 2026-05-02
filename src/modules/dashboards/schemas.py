# backend-v2/src/modules/dashboards/schemas.py
from pydantic import BaseModel
from typing import List, Optional, Any

class AdminStatsResponse(BaseModel):
    total_students: int
    total_faculty: int
    pending_enrollment_requests: int


class StudentProfileResponse(BaseModel):

    account_id:     int
    email_address:  str
    account_role:   str
    account_status: str

    # Fields the dashboard reads from profile.X
    name:           str
    student_id:     Optional[str] = None
    course:         Optional[str] = None
    year_level:     int = 1
    semester:       int = 1
    clearance:      dict = {"status": "PENDING", "details": "Enrollment request awaiting admin review"}


class OmniSearchResult(BaseModel):
    """Single item returned by GET /admin/search?q="""
    result_type: str
    result_id: int
    primary_text: str
    secondary_text: Optional[str] = None


class UserSearchResult(BaseModel):
    """Returned by GET /admin/users/search?q= and GET /admin/users"""
    account_id: int
    email_address: str
    account_role: str
    is_active_account: bool

    class Config:
        from_attributes = True


class UpdateUserStatusRequest(BaseModel):
    """Body for PATCH /admin/users/{id}/status"""
    is_active: bool


class DirectAdmissionRequest(BaseModel):
    """Body for POST /admin/students/create"""
    full_name: str
    student_number: str
    course: str
    year_level: int = 1
    email: str
    password: str


# PHASE 4 — ACADEMIC STANDING (three-tab student dashboard)
class GradeRecord(BaseModel):
    """One row in a student's grade history."""
    subject_code:      str
    subject_title:     str
    credit_units:      int
    target_year_level: int
    target_semester:   int
    midterm_grade:     Optional[float] = None
    final_grade:       Optional[float] = None
    completion_status: str


class SubjectAvailabilityResult(BaseModel):
    """Per-subject result from PrerequisiteChecker."""
    subject_id:      int
    subject_code:    str
    subject_title:   str
    credit_units:    int
    status:          str
    prereq_code:     Optional[str] = None
    prereq_title:    Optional[str] = None
    prereq_status:   Optional[str] = None
    blocking_reason: Optional[str] = None


class NextSemesterRecommendation(BaseModel):
    """Top-level PrerequisiteChecker verdict for the next semester."""
    verdict:          str
    pass_rate:        float
    available_count:  int
    blocked_count:    int
    pending_count:    int
    flagged_subjects: List[str]
    suggested_action: str
    subject_results:  List[SubjectAvailabilityResult]


class AcademicStandingResponse(BaseModel):

    student_year_level:           int
    student_semester:             int
    student_name:                 str
    current_subjects:             List[GradeRecord]
    passed_subjects:              List[GradeRecord]
    next_semester_recommendation: NextSemesterRecommendation



# PHASE 4 — ENRICHED ENROLLMENT QUEUE ITEM
class EnrollmentQueueItem(BaseModel):

    request_id:          int
    student_account_id:  int
    student_name:        Optional[str]  = None
    student_number:      Optional[str]  = None
    target_year_level:   int
    target_semester:     int
    review_status:       str
    admin_review_notes:  Optional[str]  = None
    date_submitted:      Any            = None

    # COR scan link
    document_verification_token: Optional[str] = None

    # PHASE 4: AI enrichment
    extracted_subjects:  Optional[List[str]] = None
    verification_result: Optional[Any]       = None
    ai_recommendation:   Optional[Any]       = None

    class Config:
        from_attributes = True