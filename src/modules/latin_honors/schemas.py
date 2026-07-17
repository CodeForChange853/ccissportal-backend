from pydantic import BaseModel, ConfigDict
from typing import List


class HonoreeOut(BaseModel):
    student_account_id: int
    full_name: str
    course: str
    year_level: int
    gwa: float
    honor_tier: str
    dean_note: str | None = None
    avg_rating: float = 0.0
    rating_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class RunningHonoreeOut(BaseModel):
    full_name: str
    course: str
    year_level: int
    gwa: float


class GlobalHonorsResponse(BaseModel):
    summa: List[HonoreeOut]
    magna: List[HonoreeOut]
    cum_laude: List[HonoreeOut]
    departments: List[str]


class DeanNoteRequest(BaseModel):
    student_account_id: int
    message: str


class GenerateNoteRequest(BaseModel):
    full_name: str
    gwa: float
    honor_tier: str
    course: str


class RatingRequest(BaseModel):
    session_token: str
    rating: int


class RatingOut(BaseModel):
    avg_rating: float
    rating_count: int
