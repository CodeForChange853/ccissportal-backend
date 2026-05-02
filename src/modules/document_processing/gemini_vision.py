import re
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from PIL import Image

from src.core.config import settings  
class StudentID(BaseModel):
    student_id: Optional[str] = Field(
        None, description="The alphanumeric student ID number (e.g., 2021-00123)"
    )
    full_name: Optional[str] = Field(
        None, description="The full legal name as printed on the ID"
    )
    course: Optional[str] = Field(
        None, description="The degree program or course abbreviation (e.g., BSCS)"
    )


class Subject(BaseModel):
    code: str    = Field(..., description="Subject code exactly as printed (e.g., CS 101)")
    name: str    = Field(..., description="Descriptive title of the subject")
    units: float = Field(..., description="Credit units as a number only")


class COR(BaseModel):
    subjects: List[Subject] = Field(
        ..., description="All enrolled academic subjects found on the COR."
    )
    total_units: float = Field(
        ..., description="Sum of all credit units on the COR."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Advanced Confidence Scoring Engine
# ─────────────────────────────────────────────────────────────────────────────
#
# Four weighted factors, each scored 0.0-1.0, combined into a single score:
#
#  Factor 1 - Field Completeness (30%)
#    Were all expected fields populated?
#
#  Factor 2 - Format Validity (30%)
#    Does the student ID match PH university ID pattern (YYYY-NNNNN)?
#    Do subject codes match the standard alphanumeric format?
#
#  Factor 3 - Data Consistency (25%)
#    For COR: does extracted total_units match computed sum of subjects?
#    For ID: does full_name contain at least first + last name?
#
#  Factor 4 - Content Richness (15%)
#    A COR with 1 subject is suspicious. 6-8 is a normal semester load.

_STUDENT_ID_PATTERN = re.compile(r"^\d{4}-\d{4,6}$")
_SUBJECT_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9\s\-]{1,12}$", re.IGNORECASE)


def _score_id_extraction(data: dict) -> tuple[float, dict]:
    if not data or not isinstance(data, dict):
        return 0.0, {"completeness": 0, "format_valid": 0, "consistency": 0, "richness": 0}

    expected = ["student_id", "full_name", "course"]
    filled   = [f for f in expected if data.get(f)]

    completeness = round(len(filled) / len(expected), 4)

    student_id_val = (data.get("student_id") or "").strip()
    if _STUDENT_ID_PATTERN.match(student_id_val):
        format_valid = 1.0
    elif re.search(r"\d{4}-\d+", student_id_val):
        format_valid = 0.6
    else:
        format_valid = 0.3

    name_parts = [p for p in (data.get("full_name") or "").strip().split() if p]
    consistency = 1.0 if len(name_parts) >= 2 else 0.4

    richness = 1.0 if len(filled) == 3 else (0.6 if len(filled) == 2 else 0.2)

    composite = (
        completeness * 0.30 +
        format_valid * 0.30 +
        consistency  * 0.25 +
        richness     * 0.15
    )
    breakdown = {
        "completeness": completeness,
        "format_valid": round(format_valid, 4),
        "consistency":  round(consistency, 4),
        "richness":     round(richness, 4),
    }
    return round(min(composite, 1.0), 4), breakdown


def _score_cor_extraction(data: dict) -> tuple[float, dict]:
    if not data or not isinstance(data, dict):
        return 0.0, {"completeness": 0, "format_valid": 0, "consistency": 0, "richness": 0}

    subjects: list         = data.get("subjects") or []
    total_units_raw        = data.get("total_units")

    # Safe float cast — guard against None, empty string, or non-numeric values
    try:
        total_units_stated = float(total_units_raw) if total_units_raw is not None else 0.0
    except (ValueError, TypeError):
        total_units_stated = 0.0

    has_subjects     = len(subjects) > 0
    fully_populated  = all(s.get("code") and s.get("name") and s.get("units") for s in subjects) if has_subjects else False
    completeness     = 1.0 if (has_subjects and fully_populated) else (0.5 if has_subjects else 0.0)

    if subjects:
        valid_codes  = [s for s in subjects if _SUBJECT_CODE_PATTERN.match((s.get("code") or "").strip())]
        format_valid = round(len(valid_codes) / max(len(subjects), 1), 4)
    else:
        format_valid = 0.0

    # Safe float cast for each subject's units
    computed_total = 0.0
    for s in subjects:
        try:
            computed_total += float(s.get("units") or 0)
        except (ValueError, TypeError):
            pass

    if total_units_stated > 0 and computed_total > 0:
        diff        = abs(computed_total - total_units_stated)
        denominator = max(computed_total, total_units_stated)
        consistency = 1.0 if diff <= 0.5 else round(min(computed_total, total_units_stated) / max(denominator, 0.01), 4)
    elif computed_total > 0:
        consistency = 0.7
    else:
        consistency = 0.0

    count    = len(subjects)
    richness = 1.0 if count >= 6 else (0.75 if count >= 3 else (0.4 if count >= 1 else 0.0))

    composite = (
        completeness * 0.30 +
        format_valid * 0.30 +
        consistency  * 0.25 +
        richness     * 0.15
    )
    breakdown = {
        "completeness": round(completeness, 4),
        "format_valid": round(format_valid, 4),
        "consistency":  round(consistency, 4),
        "richness":     round(richness, 4),
    }
    return round(min(composite, 1.0), 4), breakdown


# ─────────────────────────────────────────────────────────────────────────────
# Payload Validators — reject unusable extractions before they reach the DB
# ─────────────────────────────────────────────────────────────────────────────

def _validate_id_payload(data: dict) -> str | None:
    """
    Returns an error message if the ID payload is unusable, or None if valid.
    A payload is unusable if BOTH student_id and full_name are missing/empty.
    """
    if not data or not isinstance(data, dict):
        return "Extraction returned empty data. The image may be unreadable."

    student_id = (data.get("student_id") or "").strip()
    full_name  = (data.get("full_name") or "").strip()

    if not student_id and not full_name:
        return (
            "Could not extract student ID or name from the image. "
            "Please upload a clearer photo of the ID card."
        )
    return None


def _validate_cor_payload(data: dict) -> str | None:
    """
    Returns an error message if the COR payload is unusable, or None if valid.
    A payload is unusable if subjects list is empty or none have a valid code.
    """
    if not data or not isinstance(data, dict):
        return "Extraction returned empty data. The image may be unreadable."

    subjects = data.get("subjects") or []

    if not subjects:
        return (
            "No subjects could be extracted from the COR. "
            "Please upload a clearer, higher-resolution image."
        )

    # Check if at least one subject has a non-empty code
    valid_subjects = [s for s in subjects if (s.get("code") or "").strip()]
    if not valid_subjects:
        return (
            "Subjects were detected but none had readable subject codes. "
            "Please upload a clearer image of the COR."
        )

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Gemini Vision Service
# ─────────────────────────────────────────────────────────────────────────────

class GeminiVisionService:

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "CRITICAL: GEMINI_API_KEY is missing from .env. "
                "Document scanning will not work until this is set."
            )
        self.client   = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = settings.GEMINI_MODEL_ID

    def analyze(self, image_path: str, doc_type: str) -> dict:
        """
        Sends an image to Gemini Vision and returns a structured result.

        Guaranteed return contract (ScanDiffViewer.jsx depends on this shape):
        {
            "status":               "SUCCESS" | "FAILURE" | "ERROR",
            "doc_type":             "ID" | "COR",
            "extracted_data":       { ...StudentID or COR fields... },
            "confidence_score":     0.0 - 1.0,
            "confidence_breakdown": {
                "completeness":  float,
                "format_valid":  float,
                "consistency":   float,
                "richness":      float,
            },
            "model_used":           str,
            "error":                str | None,
        }
        """
        try:
            image = Image.open(image_path)

            if doc_type == "ID":
                target_schema = StudentID
                prompt = (
                    "You are an academic registrar's document scanner. "
                    "Extract student details from this university ID card. "
                    "Return null for any field that is obscured, damaged, or not visible. "
                    "Do not guess or infer values that are not clearly printed."
                )
            elif doc_type == "COR":
                target_schema = COR
                prompt = (
                    "You are an academic registrar's document scanner. "
                    "Extract only enrolled academic subjects from this Certificate of Registration (COR). "
                    "Include subject code, full subject name, and credit units for each subject. "
                    "Ignore payment amounts, fees, peso totals, and administrative rows. "
                    "Set total_units from the printed total line, not by summing yourself."
                )
            else:
                return {
                    "status": "ERROR", "doc_type": doc_type,
                    "extracted_data": {}, "confidence_score": 0.0,
                    "confidence_breakdown": {}, "model_used": self.model_id,
                    "error": f"Unsupported document type: '{doc_type}'. Must be 'ID' or 'COR'.",
                }

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[image, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=target_schema,
                ),
            )

            if not response.parsed:
                return {
                    "status": "FAILURE", "doc_type": doc_type,
                    "extracted_data": {}, "confidence_score": 0.0,
                    "confidence_breakdown": {}, "model_used": self.model_id,
                    "error": "Gemini returned an empty or unparseable response.",
                }

            extracted_data = response.parsed.model_dump()

            # ── Payload validation gate — reject unusable extractions ──
            if doc_type == "ID":
                validation_error = _validate_id_payload(extracted_data)
            else:
                validation_error = _validate_cor_payload(extracted_data)

            if validation_error:
                # Still score it so the frontend can show diagnostics
                if doc_type == "ID":
                    confidence_score, breakdown = _score_id_extraction(extracted_data)
                else:
                    confidence_score, breakdown = _score_cor_extraction(extracted_data)

                return {
                    "status":               "FAILURE",
                    "doc_type":             doc_type,
                    "extracted_data":       extracted_data,
                    "confidence_score":     confidence_score,
                    "confidence_breakdown": breakdown,
                    "model_used":           self.model_id,
                    "error":                validation_error,
                }

            if doc_type == "ID":
                confidence_score, breakdown = _score_id_extraction(extracted_data)
            else:
                confidence_score, breakdown = _score_cor_extraction(extracted_data)

            return {
                "status":               "SUCCESS",
                "doc_type":             doc_type,
                "extracted_data":       extracted_data,
                "confidence_score":     confidence_score,
                "confidence_breakdown": breakdown,
                "model_used":           self.model_id,
                "error":                None,
            }

        except Exception as error:
            from google.api_core.exceptions import ResourceExhausted
            if isinstance(error, ResourceExhausted):
                raise error

            return {
                "status": "ERROR", "doc_type": doc_type,
                "extracted_data": {}, "confidence_score": 0.0,
                "confidence_breakdown": {}, "model_used": getattr(self, "model_id", "unknown"),
                "error": str(error),
            }