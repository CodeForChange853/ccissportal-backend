import re
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _check_password_strength(v: str) -> str:
    """Shared password strength rule: uppercase + digit + special char."""
    if not re.search(r'[A-Z]', v):
        raise ValueError('must contain at least one uppercase letter')
    if not re.search(r'\d', v):
        raise ValueError('must contain at least one number')
    if not re.search(r'[^a-zA-Z0-9]', v):
        raise ValueError('must contain at least one special character')
    return v


class LoginCredentialsRequest(BaseModel):
    email_address: EmailStr = Field(..., max_length=150)
    plain_text_password: str = Field(..., min_length=8, max_length=100)


class SuccessfulLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_role: str

    account_id: int | None = None


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegistrationRequest(BaseModel):
    email_address: EmailStr = Field(..., max_length=150)
    plain_text_password: str = Field(..., min_length=8, max_length=100)
    passkey_code: str | None = Field(None, max_length=50)
    id_verification_token: str | None = Field(None, max_length=100)
    cor_verification_token: str | None = Field(None, max_length=100)
    account_role: str | None = Field("STUDENT", max_length=20)

    #  Profile fields

    first_name:          str | None = Field(None, max_length=100)
    last_name:           str | None = Field(None, max_length=100)

    # Student-specific
    student_number:      str | None = Field(None, max_length=50)
    course:              str | None = Field(None, max_length=100)

    # Faculty-specific
    employee_id:         str | None = Field(None, max_length=50)
    academic_department: str | None = Field(None, max_length=150)

    @field_validator('plain_text_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class PreRegistrationValidationRequest(BaseModel):
    student_number: str
    passkey_code: str


class ProfileResponse(BaseModel):
    """Returned by GET /authentication/me."""
    account_id: int
    email_address: str
    account_role: str
    is_active_account: bool

    model_config = ConfigDict(from_attributes=True)


# ── Wall of Shame Schemas ──

class ViolationEntry(BaseModel):
    offense: str
    detected_at: str
    keywords: list | None = None

class ViolatorPublicProfile(BaseModel):
    """Public-facing violator card on the Wall of Shame."""
    account_id: int
    display_name: str
    role: str
    violation_count: int
    last_violation_at: str | None = None
    violation_log: list[ViolationEntry] = []
    days_until_eligible: int = 0
    eligible_for_removal: bool = False

class UnderwatchProfile(BaseModel):
    """Admin-only: users with 1-2 strikes."""
    account_id: int
    display_name: str
    role: str
    violation_count: int
    last_violation_at: str | None = None
    violation_log: list[ViolationEntry] = []


# ── Secretary Provisioning Schemas ──

class SecretaryProvisionRequest(BaseModel):
    email_address: EmailStr = Field(..., max_length=150)
    plain_text_password: str = Field(..., min_length=8, max_length=100)
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)

    @field_validator('plain_text_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _check_password_strength(v)


class SecretaryProvisionResponse(BaseModel):
    account_id: int
    email_address: str
    account_role: str
    is_active_account: bool
    message: str

    model_config = ConfigDict(from_attributes=True)