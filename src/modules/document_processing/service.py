# backend-v2/src/modules/document_processing/service.py
import os
import json
from typing import Optional
from sqlalchemy.orm import Session

from . import repository
from .gemini_vision import GeminiVisionService
from src.modules.audit import service as audit_service

from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from google.api_core.exceptions import ResourceExhausted

def get_gemini_service() -> GeminiVisionService:
    return GeminiVisionService()

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=10, max=60),
    retry=retry_if_exception_type(ResourceExhausted),
    reraise=True
)
def _call_gemini_with_retry(gemini_service, file_path: str, document_type: str):
    return gemini_service.analyze(image_path=file_path, doc_type=document_type)

# last finish is 3
def execute_background_ai_scan(
    file_path: str,
    scan_token: str,
    document_type: str,
    student_account_id: Optional[int],
    actor_id: Optional[int],
    actor_email: Optional[str],
    ip_address: Optional[str],
):
    from src.core.database_setup import SessionLocal
    database_session = SessionLocal()
    
    scan_status      = "ERROR"
    confidence_score = None

    try:
        try:
            gemini_service = get_gemini_service()
        except Exception:
            gemini_service = None

        if gemini_service is None:
            repository.update_scan_completion(
                database_session=database_session,
                token=scan_token,
                error_msg="Document scanning unavailable: GEMINI_API_KEY not configured.",
            )
            return

        # ── Step 1: Gemini Vision extraction ──────────────────────────────────
        try:
            result = _call_gemini_with_retry(gemini_service, file_path, document_type)
        except ResourceExhausted as e:
            repository.update_scan_completion(
                database_session=database_session,
                token=scan_token,
                error_msg=f"The AI service is temporarily overloaded after multiple retries. Details: {str(e)}",
                status="ERROR"
            )
            return

        if result["status"] != "SUCCESS":
            repository.update_scan_completion(
                database_session=database_session,
                token=scan_token,
                error_msg=result.get("error") or f"Extraction status: {result['status']}",
                document_type=document_type,
            )
            return

        scan_status      = "SUCCESS"
        confidence_score = result["confidence_score"]
        extracted_data   = result["extracted_data"]

        # ── Step 2: Prerequisite check (COR only) ─────────────────────────────
        verification_result = None
        ai_recommendation   = None

        if document_type == "COR" and student_account_id is not None:
            try:
                from src.modules.enrollment.prerequisite_checker import PrerequisiteChecker

                subjects_list = extracted_data.get("subjects", [])
                subject_codes = [
                    s["code"] for s in subjects_list if s.get("code")
                ]

                if subject_codes:
                    checker = PrerequisiteChecker(database_session)
                    rec     = checker.check_subjects(
                        student_account_id=student_account_id,
                        subject_codes=subject_codes,
                    )

                    verification_result = [
                        {
                            "subject_id":      r.subject_id,
                            "subject_code":    r.subject_code,
                            "subject_title":   r.subject_title,
                            "credit_units":    r.credit_units,
                            "status":          r.status,
                            "prereq_code":     r.prereq_code,
                            "prereq_title":    r.prereq_title,
                            "prereq_status":   r.prereq_status,
                            "blocking_reason": r.blocking_reason,
                        }
                        for r in rec.subject_results
                    ]

                    ai_recommendation = {
                        "verdict":          rec.verdict,
                        "pass_rate":        rec.pass_rate,
                        "available_count":  rec.available_count,
                        "blocked_count":    rec.blocked_count,
                        "pending_count":    rec.pending_count,
                        "flagged_subjects": rec.flagged_subjects,
                        "suggested_action": rec.suggested_action,
                    }
                    print(
                        f"✅ PrerequisiteChecker: {len(subject_codes)} subjects "
                        f"for student #{student_account_id} → verdict: {rec.verdict}"
                    )

            except Exception as checker_err:
                print(f"⚠️  PrerequisiteChecker error (non-fatal): {checker_err}")
                ai_recommendation = {
                    "verdict":          "ERROR",
                    "suggested_action": f"Prerequisite check failed: {str(checker_err)}",
                    "flagged_subjects": [],
                    "pass_rate":        0.0,
                    "available_count":  0,
                    "blocked_count":    0,
                    "pending_count":    0,
                }

        # ── Step 3: Persist full payload ───────────────────────────────────────
        full_payload = json.dumps({
            "doc_type":             result["doc_type"],
            "extracted_data":       extracted_data,
            "confidence_score":     confidence_score,
            "confidence_breakdown": result["confidence_breakdown"],
            "model_used":           result["model_used"],
            "verification_result":  verification_result,
            "ai_recommendation":    ai_recommendation,
        })

        repository.update_scan_completion(
            database_session=database_session,
            token=scan_token,
            extracted_data=full_payload,
            confidence_score=confidence_score,
            document_type=document_type,
        )

    except Exception as unexpected_error:
        repository.update_scan_completion(
            database_session=database_session,
            token=scan_token,
            error_msg=f"Unexpected error during scan: {str(unexpected_error)}",
        )

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🔒 Privacy: '{file_path}' deleted after processing.")

        audit_service.log_event(
            database_session=database_session,
            event_type="DOCUMENT_SCANNED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_type="document",
            target_id=scan_token,
            ip_address=ip_address,
            payload={
                "doc_type":         document_type,
                "status":           scan_status,
                "confidence_score": confidence_score,
            },
        )
        database_session.close()