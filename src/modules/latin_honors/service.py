from sqlalchemy.orm import Session
from google import genai

from src.core.config import settings
from src.modules.latin_honors import repository


def get_global_honors(db: Session) -> dict:
    students = repository.get_honors_students(db)
    departments = repository.get_all_departments(db)
    return {
        "summa":      [s for s in students if s["honor_tier"] == "SUMMA_CUM_LAUDE"],
        "magna":      [s for s in students if s["honor_tier"] == "MAGNA_CUM_LAUDE"],
        "cum_laude":  [s for s in students if s["honor_tier"] == "CUM_LAUDE"],
        "departments": departments,
    }


def get_department_honors(db: Session, course: str) -> dict:
    students = repository.get_honors_students(db, course_filter=course)
    return {
        "summa":     [s for s in students if s["honor_tier"] == "SUMMA_CUM_LAUDE"],
        "magna":     [s for s in students if s["honor_tier"] == "MAGNA_CUM_LAUDE"],
        "cum_laude": [s for s in students if s["honor_tier"] == "CUM_LAUDE"],
        "department": course,
    }


def get_running_for_honors(db: Session) -> list:
    return repository.get_running_for_honors(db)


def save_dean_note(db: Session, student_account_id: int, message: str, admin_id: int):
    return repository.upsert_dean_note(db, student_account_id, message, admin_id)


def remove_dean_note(db: Session, student_account_id: int):
    repository.delete_dean_note(db, student_account_id)


def submit_rating(db: Session, student_account_id: int, session_token: str, rating: int) -> dict:
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be between 1 and 5.")
    return repository.submit_rating(db, student_account_id, session_token, rating)


def generate_ai_note(full_name: str, gwa: float, honor_tier: str, course: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured.")

    tier_display = {
        "SUMMA_CUM_LAUDE": "Summa Cum Laude",
        "MAGNA_CUM_LAUDE": "Magna Cum Laude",
        "CUM_LAUDE":       "Cum Laude",
    }.get(honor_tier, honor_tier.replace("_", " ").title())

    prompt = (
        f"You are the Dean of the College of Computing and Information Sciences. "
        f"Write a warm, inspiring, and personalized recognition note for a graduating student "
        f"who has achieved Latin Honors. Requirements:\n"
        f"- Exactly 2–3 sentences.\n"
        f"- Heartfelt, encouraging, and premium — not generic.\n"
        f"- Mention their specific honor tier ({tier_display}) naturally.\n"
        f"- End with a forward-looking statement about their future.\n"
        f"- Do NOT add a salutation or signature — just the note body.\n\n"
        f"Student details:\n"
        f"  Name: {full_name}\n"
        f"  Program: {course}\n"
        f"  Honor Tier: {tier_display}\n"
        f"  GWA: {gwa:.2f}\n\n"
        f"Write only the note text."
    )

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL_ID,
        contents=prompt,
    )
    return response.text.strip()


def get_admin_honors_list(db: Session) -> list:
    return repository.get_admin_honors_list(db)
