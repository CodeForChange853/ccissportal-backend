from pydantic import BaseModel
from typing import Optional, Any
from typing import List


# ENROLLMENT SUBMISSION / APPROVAL
class StudentEnrollmentSubmission(BaseModel):
    target_year_level: int
    target_semester:   int
    document_verification_token: Optional[str] = None
    extracted_subjects: Optional[list[str]] = None


class AdminApprovalDecision(BaseModel):
    decision_status: str         
    admin_notes:     Optional[str] = None

class BulkAdminApprovalDecision(BaseModel):
    request_ids: List[int]
    decision_status: str
    admin_notes: Optional[str] = None


# CURRICULUM SUBJECT RESPONSES
class SubjectResponse(BaseModel):
    subject_id:             int
    subject_code:           str
    subject_title:          str
    credit_units:           int
    target_year_level:      int
    target_semester:        int
    course:                 str  = "BSCS"
    prerequisite_subject_id: Optional[int] = None

    class Config:
        from_attributes = True


class CurriculumSubjectCreateRequest(BaseModel):
    subject_code:      str
    subject_title:     str
    credit_units:      int
    target_year_level: int
    target_semester:   int
    course:            str           = "BSCS"
    prerequisite_subject_id: Optional[int] = None


class CurriculumSubjectUpdateRequest(BaseModel):
    subject_code:      Optional[str] = None
    subject_title:     Optional[str] = None
    credit_units:      Optional[int] = None
    target_year_level: Optional[int] = None
    target_semester:   Optional[int] = None
    course:            Optional[str] = None
    prerequisite_subject_id: Optional[int] = None


# PHASE 1 — PREREQUISITE CHECKER RESPONSE TYPES
class SubjectAvailabilityResult(BaseModel):

    subject_id:      int
    subject_code:    str
    subject_title:   str
    credit_units:    int
    status:          str
    prereq_code:     Optional[str]  = None   
    prereq_title:    Optional[str]  = None   
    prereq_status:   Optional[str]  = None   
    blocking_reason: Optional[str]  = None   


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
    midterm_grade:      Optional[float] = None
    final_grade:        Optional[float] = None
    completion_status:  str

    class Config:
        from_attributes = True


class AcademicStandingResponse(BaseModel):
   
    student_year_level: int
    student_semester:   int

    current_subjects:   list[GradeRecord]

    passed_subjects:    list[GradeRecord]

    next_semester_recommendation: EnrollmentRecommendation