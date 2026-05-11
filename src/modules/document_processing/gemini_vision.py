import re
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import APIError
from PIL import Image

from src.core.config import settings  
class StudentID(BaseModel):
    is_valid_document: bool = Field(
        ..., description="True if the image is actually a valid university/school ID card. False if it is a random object, animal, or person's face only."
    )
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
    is_valid_document: bool = Field(
        ..., description="True if the image is actually a valid Certificate of Registration (COR). False if it is a random object, animal, or person's face only."
    )
    subjects: List[Subject] = Field(
        ..., description="All enrolled academic subjects found on the COR."
    )
    total_units: float = Field(
        ..., description="Sum of all credit units on the COR."
    )




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

    if not data.get("is_valid_document"):
        return (
            "The uploaded image does not appear to be a valid Student ID card. "
            "Please upload a clear photo of your school ID."
        )

    student_id = (data.get("student_id") or "").strip()
    full_name  = (data.get("full_name") or "").strip()

    if not student_id and not full_name:
        return (
            "Could not extract student ID or name from the image. "
            "Please upload a clearer photo of the ID card."
        )
    return None


def _validate_cor_payload(data: dict) -> str | None:
    if not data or not isinstance(data, dict):
        return "Extraction returned empty data. The image may be unreadable."

    if not data.get("is_valid_document"):
        return (
            "The uploaded image does not appear to be a valid Certificate of Registration (COR). "
            "Please upload a clear, high-resolution document."
        )

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
        """
        try:
            # Ensure the image file is closed properly after loading into memory
            with Image.open(image_path) as img:
                # Convert to RGB to avoid issues with PNG alpha channels
                image = img.convert("RGB") 

            if doc_type == "ID":
                target_schema = StudentID
                prompt = (
                    "You are an academic registrar's document scanner. "
                    "Analyze the provided image and set is_valid_document to TRUE if and only if "
                    "the image contains a physical or digital University/School ID card with readable text. "
                    "If the image is just a person's face (selfie), an animal (like a monkey), or any random object, "
                    "set is_valid_document to FALSE. "
                    "If valid, extract student details: student_id, full_name, and course. "
                    "Return null for any field that is obscured or not visible. Do not guess values."
                )
            elif doc_type == "COR":
                target_schema = COR
                prompt = (
                    "You are an academic registrar's document scanner. "
                    "Set is_valid_document to TRUE if the image is a Certificate of Registration (COR). "
                    "If it is not a document, set is_valid_document to FALSE. "
                    "If valid, extract only enrolled academic subjects with their code, name, and credit units. "
                    "Ignore payment amounts and administrative rows. Set total_units from the printed total line."
                )
            else:
                return {
                    "status": "ERROR", "doc_type": doc_type,
                    "extracted_data": {}, "confidence_score": 0.0,
                    "confidence_breakdown": {}, "model_used": self.model_id,
                    "error": f"Unsupported document type: '{doc_type}'. Must be 'ID' or 'COR'.",
                }

            # 1. Define the config once (DRY principle)
            extraction_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=target_schema,
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_LOW_AND_ABOVE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_LOW_AND_ABOVE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_LOW_AND_ABOVE"),
                ]
            )

            # 2. Primary attempt
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=[image, prompt],
                    config=extraction_config,
                )
            except APIError as e:
                # 3. Fallback attempt using the EXACT SAME config
                print(f"Primary model {self.model_id} failed: {str(e)}. Attempting fallback...")
                response = self.client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=[image, prompt],
                    config=extraction_config,
                )

            # 4. Check for empty parsed response
            if not response.parsed:
                return {
                    "status": "FAILURE", "doc_type": doc_type,
                    "extracted_data": {}, "confidence_score": 0.0,
                    "confidence_breakdown": {}, "model_used": self.model_id,
                    "error": "Gemini returned an empty or unparseable response.",
                }

            extracted_data = response.parsed.model_dump()

            # 5. Payload validation gate
            if doc_type == "ID":
                validation_error = _validate_id_payload(extracted_data)
                confidence_score, breakdown = _score_id_extraction(extracted_data)
            else:
                validation_error = _validate_cor_payload(extracted_data)
                confidence_score, breakdown = _score_cor_extraction(extracted_data)

            if validation_error:
                return {
                    "status":               "FAILURE",
                    "doc_type":             doc_type,
                    "extracted_data":       extracted_data,
                    "confidence_score":     confidence_score,
                    "confidence_breakdown": breakdown,
                    "model_used":           self.model_id,
                    "error":                validation_error,
                }

            # 6. Success state
            return {
                "status":               "SUCCESS",
                "doc_type":             doc_type,
                "extracted_data":       extracted_data,
                "confidence_score":     confidence_score,
                "confidence_breakdown": breakdown,
                "model_used":           self.model_id,
                "error":                None,
            }

        except APIError as api_error:
            # Correctly handle modern SDK API errors (like Quota Exceeded)
            error_msg = f"API Error: {api_error.message}" if hasattr(api_error, "message") else str(api_error)
            print(f"API Exhausted or Failed: {error_msg}")
            return {
                "status": "ERROR", "doc_type": doc_type,
                "extracted_data": {}, "confidence_score": 0.0,
                "confidence_breakdown": {}, "model_used": getattr(self, "model_id", "unknown"),
                "error": error_msg,
            }
            
        except Exception as error:
            # Catch all other local python errors (e.g. image read failure)
            print(f"Local Processing Error: {str(error)}")
            return {
                "status": "ERROR", "doc_type": doc_type,
                "extracted_data": {}, "confidence_score": 0.0,
                "confidence_breakdown": {}, "model_used": getattr(self, "model_id", "unknown"),
                "error": str(error),
            }