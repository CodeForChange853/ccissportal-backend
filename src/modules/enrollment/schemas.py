from pydantic import BaseModel, ConfigDict
from typing import Any
from typing import List


# ENROLLMENT SUBMISSION / APPROVAL
class StudentEnrollmentSubmission(BaseModel):
    target_year_level: int
    target_semester:   int
    document_verification_token: str | None = None
    extracted_subjects: list[str] | None = None


class AdminApprovalDecision(BaseModel):
    decision_status: str         
    admin_notes:     str | None = None

class BulkAdminApprovalDecision(BaseModel):
    request_ids: List[int]
    decision_status: str
    admin_notes: str | None = None


# CURRICULUM SUBJECT RESPONSES
class SubjectResponse(BaseModel):
    subject_id:             int
    subject_code:           str
    subject_title:          str
    credit_units:           int
    target_year_level:      int
    target_semester:        int
    course:                 str  = "BSCS"
    prerequisite_subject_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CurriculumSubjectCreateRequest(BaseModel):
    subject_code:      str
    subject_title:     str
    credit_units:      int
    target_year_level: int
    target_semester:   int
    course:            str           = "BSCS"
    prerequisite_subject_id: int | None = None


class CurriculumSubjectUpdateRequest(BaseModel):
    subject_code:      str | None = None
    subject_title:     str | None = None
    credit_units:      int | None = None
    target_year_level: int | None = None
    target_semester:   int | None = None
    course:            str | None = None
    prerequisite_subject_id: int | None = None


# SE-03 — Prerequisite dependency graph
class PrereqNode(BaseModel):
    id:    int
    code:  str
    title: str
    year:  int
    sem:   int
    units: int
    course: str

class PrereqEdge(BaseModel):
    source: int   # prerequisite subject_id
    target: int   # dependent subject_id (the one that requires source)

class PrereqGraphResponse(BaseModel):
    nodes: List[PrereqNode]
    edges: List[PrereqEdge]


# PHASE 1 — PREREQUISITE CHECKER RESPONSE TYPES
class SubjectAvailabilityResult(BaseModel):

    subject_id:      int
    subject_code:    str
    subject_title:   str
    credit_units:    int
    status:          str
    prereq_code:     str | None  = None
    prereq_title:    str | None  = None
    prereq_status:   str | None  = None
    blocking_reason: str | None  = None
    priority_score:  int | None  = None   # SE-05: 0-100 ranking score for AVAILABLE subjects


class EnrollmentRecommendation(BaseModel):
 
    verdict:          str                             
    pass_rate:        float                            
    available_count:  int
    blocked_count:    int
    pending_count:    int
    flagged_subjects: list[str]                        
    suggested_action: str                              
    subject_results:  list[SubjectAvailabilityResult] 


# PHASE 1 — STUDENT ACADEMIC STANDING (three-tab dashboard payload)
class GradeRecord(BaseModel):
    subject_code:       str
    subject_title:      str
    credit_units:       int
    target_year_level:  int
    target_semester:    int
    midterm_grade:      float | None = None
    final_grade:        float | None = None
    completion_status:  str

    model_config = ConfigDict(from_attributes=True)


class AcademicStandingResponse(BaseModel):

    student_year_level: int
    student_semester:   int

    current_subjects:   list[GradeRecord]

    passed_subjects:    list[GradeRecord]

    next_semester_recommendation: EnrollmentRecommendation


# SE-04 — At-Risk Early Warning
class AtRiskBreakdown(BaseModel):
    failed_load_score:  int
    gwa_score:          int
    variance_score:     int
    consultation_score: int


class AtRiskAssessmentResponse(BaseModel):
    student_account_id:   int
    risk_score:           int
    risk_level:           str   # HIGH | MODERATE | LOW
    breakdown:            AtRiskBreakdown
    interventions:        List[str]
    gwa:                  float | None = None
    failed_major_count:   int
    failed_minor_count:   int
    has_any_consultation: bool


class AdminAtRiskStudentItem(BaseModel):
    student_account_id: int
    student_name:       str
    student_number:     str | None = None
    email_address:      str
    risk_score:         int
    risk_level:         str
    top_intervention:   str | None = None
    failed_major_count: int
    gwa:                float | None = None


# ── Admin: Student Records (read-only roster) ─────────────────────────────────

class StudentRecordItem(BaseModel):
    student_account_id:        int
    student_name:              str
    student_number:            str | None  = None
    course:                    str | None  = None
    year_level:                int | None  = None
    semester:                  int | None  = None
    latest_enrollment_status:  str | None  = None
    latest_cor_release_status: str | None  = None
    is_irregular:              bool           = False