# backend-v2/src/modules/document_processing/service.py

import os
import json
import shutil
from typing import Optional
from sqlalchemy.orm import Session

from . import repository
from .gemini_vision import GeminiVisionService
from .repository import CONFIDENCE_THRESHOLD, CONFIDENCE_FLOOR
from src.modules.audit import service as audit_service

from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from google.api_core.exceptions import ResourceExhausted

# ─────────────────────────────────────────────────────────────────────────────
# Status routing thresholds (imported from repository so there is ONE source)
# ─────────────────────────────────────────────────────────────────────────────
#   confidence ≥ CONFIDENCE_THRESHOLD  → COMPLETED     (cached, auto-accepted)
#   CONFIDENCE_FLOOR ≤ c < THRESHOLD   → NEEDS_REVIEW  (held for human review)
#   confidence < CONFIDENCE_FLOOR      → FAILED        (student must re-upload)

REVIEW_QUEUE_DIR = "review_queue"


def get_gemini_service() -> GeminiVisionService:
    return GeminiVisionService()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=10, max=60),
    retry=retry_if_exception_type(ResourceExhausted),
    reraise=True,
)
def _call_gemini_with_retry(gemini_service, file_path: str, document_type: str):
    return gemini_service.analyze(image_path=file_path, doc_type=document_type)


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
    retain_path      = None   # Path in review_queue/ — set only for NEEDS_REVIEW

    try:
        # ── Step 0: Initialise Gemini ─────────────────────────────────────────
        try:
            gemini_service = get_gemini_service()
        except Exception:
            gemini_service = None

        if gemini_service is None:
            repository.update_scan_completion(
                database_session=database_session,
                token=scan_token,
                error_msg="Document scanning unavailable: GEMINI_API_KEY not configured.",
                status="ERROR",
            )
            return

        # ── Step 1: Gemini Vision extraction ─────────────────────────────────
        try:
            result = _call_gemini_with_retry(gemini_service, file_path, document_type)
        except ResourceExhausted as e:
            repository.update_scan_completion(
                database_session=database_session,
                token=scan_token,
                error_msg=f"The AI service is temporarily overloaded after multiple retries. Details: {str(e)}",
                status="ERROR",
            )
            return

        if result["status"] != "SUCCESS":
            repository.update_scan_completion(
                database_session=database_session,
                token=scan_token,
                error_msg=result.get("error") or f"Extraction status: {result['status']}",
                document_type=document_type,
                status="FAILED",
            )
            return

        scan_status      = "SUCCESS"
        confidence_score = result["confidence_score"]
        extracted_data   = result["extracted_data"]

        # ── Step 2: Confidence-based status routing ───────────────────────────
        if confidence_score >= CONFIDENCE_THRESHOLD:
            final_status = "COMPLETED"
        elif confidence_score >= CONFIDENCE_FLOOR:
            final_status = "NEEDS_REVIEW"
            # Retain a copy of the source file so admin/secretary can see the
            # original document in the verification queue side-panel.
            # NOTE: This is a *copy* — temp_uploads/ file is still cleaned up in
            # the finally block below. review_queue/ has its own lifecycle
            # (file deleted when record is MANUALLY_VERIFIED via apply_manual_correction).
            os.makedirs(REVIEW_QUEUE_DIR, exist_ok=True)
            retain_path = os.path.abspath(f"{REVIEW_QUEUE_DIR}/{scan_token}.jpg")
            shutil.copy(file_path, retain_path)
            print(f"NEEDS_REVIEW: image retained at '{retain_path}' for human verification.")
        else:
            # Confidence below the floor — extraction is too poor to queue for review.
            # Prompt the student to re-upload a clearer image instead.
            scan_status = "LOW_CONFIDENCE"
            repository.update_scan_completion(
                database_session=database_session,
                token=scan_token,
                error_msg=(
                    f"Extraction confidence too low ({int(confidence_score * 100)}%). "
                    "Please re-upload a clearer, higher-resolution image of your document."
                ),
                document_type=document_type,
                status="FAILED",
            )
            return

        # ── Step 3: Prerequisite check (COR + COMPLETED/NEEDS_REVIEW only) ───
        verification_result = None
        ai_recommendation   = None

        if document_type == "COR" and student_account_id is not None:
            try:
                from src.modules.enrollment.prerequisite_checker import PrerequisiteChecker

                subjects_list = extracted_data.get("subjects", [])
                subject_codes = [s["code"] for s in subjects_list if s.get("code")]

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
                        f"PrerequisiteChecker: {len(subject_codes)} subjects "
                        f"for student #{student_account_id} → verdict: {rec.verdict}"
                    )

            except Exception as checker_err:
                database_session.rollback()
                print(f"PrerequisiteChecker error (non-fatal): {checker_err}")
                ai_recommendation = {
                    "verdict":          "ERROR",
                    "suggested_action": f"Prerequisite check failed: {str(checker_err)}",
                    "flagged_subjects": [],
                    "pass_rate":        0.0,
                    "available_count":  0,
                    "blocked_count":    0,
                    "pending_count":    0,
                }

        # ── Step 4: Persist full payload ──────────────────────────────────────
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
            status=final_status,             # ← COMPLETED or NEEDS_REVIEW
            review_image_path=retain_path,   # ← None for COMPLETED; path for NEEDS_REVIEW
        )

    except Exception as unexpected_error:
        database_session.rollback()
        repository.update_scan_completion(
            database_session=database_session,
            token=scan_token,
            error_msg=f"Unexpected error during scan: {str(unexpected_error)}",
            status="ERROR",
        )

    finally:
        # Always delete the TEMP file (temp_uploads/).
        # The review_queue/ copy (retain_path) is intentionally NOT deleted here —
        # it has its own lifecycle managed by apply_manual_correction().
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Privacy: '{file_path}' deleted from temp_uploads after processing.")

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
