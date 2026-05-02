# backend-v2/src/modules/auth/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginCredentialsRequest(BaseModel):
    email_address: EmailStr
    plain_text_password: str


class SuccessfulLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_role: str

    account_id: Optional[int] = None


class RegistrationRequest(BaseModel):
    email_address: EmailStr
    plain_text_password: str
    passkey_code: Optional[str] = None
    document_verification_token: Optional[str] = None
    account_role: Optional[str] = "STUDENT"

    #  Profile fields 

    first_name:          Optional[str] = None
    last_name:           Optional[str] = None

    # Student-specific
    student_number:      Optional[str] = None   
    course:              Optional[str] = None   

    # Faculty-specific
    employee_id:         Optional[str] = None  
    academic_department: Optional[str] = None  


class ProfileResponse(BaseModel):
    """Returned by GET /authentication/me."""
    account_id: int
    email_address: str
    account_role: str
    is_active_account: bool

    class Config:
        from_attributes = True