from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class LoginCredentialsRequest(BaseModel):
    email_address: EmailStr = Field(..., max_length=150)
    plain_text_password: str = Field(..., min_length=8, max_length=100)


class SuccessfulLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_role: str

    account_id: Optional[int] = None


class RegistrationRequest(BaseModel):
    email_address: EmailStr = Field(..., max_length=150)
    plain_text_password: str = Field(..., min_length=8, max_length=100)
    passkey_code: Optional[str] = Field(None, max_length=50)
    document_verification_token: Optional[str] = Field(None, max_length=100)
    account_role: Optional[str] = Field("STUDENT", max_length=20)

    #  Profile fields 

    first_name:          Optional[str] = Field(None, max_length=100)
    last_name:           Optional[str] = Field(None, max_length=100)

    # Student-specific
    student_number:      Optional[str] = Field(None, max_length=50)   
    course:              Optional[str] = Field(None, max_length=100)   

    # Faculty-specific
    employee_id:         Optional[str] = Field(None, max_length=50)  
    academic_department: Optional[str] = Field(None, max_length=150)  


class PreRegistrationValidationRequest(BaseModel):
    student_number: str
    passkey_code: str


class ProfileResponse(BaseModel):
    """Returned by GET /authentication/me."""
    account_id: int
    email_address: str
    account_role: str
    is_active_account: bool

    class Config:
        from_attributes = True