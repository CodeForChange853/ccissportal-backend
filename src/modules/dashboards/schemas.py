# backend-v2/src/modules/dashboards/schemas.py
from pydantic import BaseModel, ConfigDict
from typing import List, Any
from src.modules.enrollment.schemas import GradeRecord, SubjectAvailabilityResult  # noqa: F401 — re-exported

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
    student_id:     str | None = None
    course:         str | None = None
    year_level:     int = 1
    semester:       int = 1
    clearance:      dict = {"status": "PENDING", "details": "Enrollment request awaiting admin review"}
    was_reformed:   bool = False  # True if user was previously on the Wall of Shame and reformed


class OmniSearchResult(BaseModel):
    """Single item returned by GET /admin/search?q="""
    result_type: str                      # STUDENT | FACULTY | SUBJECT | ACTION
    result_id: int                        # entity PK, or 0 for system-level actions
    primary_text: str
    secondary_text: str | None = None
    relevance_score: float = 1.0
    action_type: str | None = None    # SUSPEND_USER | ACTIVATE_USER | MAINTENANCE_ON | MAINTENANCE_OFF


class UserSearchResult(BaseModel):
    """Returned by GET /admin/users/search?q= and GET /admin/users"""
    account_id: int
    email_address: str
    account_role: str
    is_active_account: bool

    model_config = ConfigDict(from_attributes=True)


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


class BackSubjectRecord(BaseModel):
    """A failed subject recommended for retake."""
    subject_id:      int
    subject_code:    str
    subject_title:   str
    credit_units:    int
    subject_type:    str              # MAJOR | MINOR | SPECIAL
    times_failed:    int
    blocking_reason: str | None = None


class RetentionStatus(BaseModel):
    """Academic retention standing."""
    status:                str        # GOOD | AT_RISK | UNDER_RETENTION | DROPOUT_RISK
    message:               str
    at_risk_major_count:   int  = 0
    failed_units:          int  = 0


class AcademicStandingResponse(BaseModel):

    student_year_level:           int
    student_semester:             int
    student_name:                 str
    is_irregular:                 bool              = False
    current_subjects:             List[GradeRecord]
    passed_subjects:              List[GradeRecord]
    next_semester_recommendation: NextSemesterRecommendation
    back_subjects:                List[BackSubjectRecord]    = []
    retention_status:             RetentionStatus | None = None



# PHASE 4 — ENRICHED ENROLLMENT QUEUE ITEM
class EnrollmentQueueItem(BaseModel):

    request_id:          int
    student_account_id:  int
    student_name:        str | None  = None
    student_number:      str | None  = None
    target_year_level:   int
    target_semester:     int
    review_status:       str
    admin_review_notes:  str | None  = None
    date_submitted:      Any            = None

    # COR scan link
    document_verification_token: str | None = None

    # PHASE 4: AI enrichment
    extracted_subjects:  List[str] | None = None
    verification_result: Any | None       = None
    ai_recommendation:   Any | None       = None

    model_config = ConfigDict(from_attributes=True)