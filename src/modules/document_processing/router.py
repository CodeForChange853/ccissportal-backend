import shutil
import uuid
import os
import json
import hashlib

from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import schemas, service, repository
from src.core.database_setup import get_database_session
from src.core.security import get_current_user, get_optional_current_user
from src.modules.auth.models import UserAccount

document_router = APIRouter(
    prefix="/documents",
    tags=["AI Document Scanning"]
)

os.makedirs("temp_uploads", exist_ok=True)


@document_router.post("/scan/{document_type}", response_model=schemas.ScanInitiationResponse)
def upload_and_scan_document(
    request: Request,
    document_type: str,
    background_tasks: BackgroundTasks,
    uploaded_file: UploadFile = File(...),
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount | None = Depends(get_optional_current_user),
):
    # ── 1. Validate File Size (5MB Limit) ─────────────────────────────
    MAX_SIZE = 5 * 1024 * 1024  # 5MB
    uploaded_file.file.seek(0, os.SEEK_END)
    file_size = uploaded_file.file.tell()
    uploaded_file.file.seek(0)
    
    if file_size > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({file_size} bytes). Maximum allowed is 5MB."
        )

    # ── 2. Validate MIME Type ──────────────────────────────────────────
    ALLOWED_TYPES = ["image/jpeg", "image/png", "application/pdf"]
    if uploaded_file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid file type '{uploaded_file.content_type}'. Only JPG, PNG, and PDF are allowed."
        )

    # ── 3. Calculate File Hash (SHA-256) for Deduplication Cache ──
    file_content = uploaded_file.file.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    uploaded_file.file.seek(0) # Reset pointer after reading

    # ── 4. Check Deduplication Cache (Fast Reuse Path) ──
    existing_scan = repository.fetch_successful_scan_by_hash(database_session, file_hash, document_type)
    
    if existing_scan:
        # Generate a NEW token but REUSE the data immediately
        new_token = str(uuid.uuid4())
        repository.create_initial_scan_record(database_session, new_token, file_hash)
        repository.update_scan_completion(
            database_session=database_session,
            token=new_token,
            extracted_data=existing_scan.extracted_ai_data,
            confidence_score=existing_scan.confidence_score,
            document_type=document_type
        )
        
        return schemas.ScanInitiationResponse(
            secure_scan_token=new_token,
            processing_status="COMPLETED", # Near-instant reuse!
            message="Document fingerprint recognized. Reusing previous verified analysis.",
        )

    # ── 5. Standard Background Processing Path ──
    secure_token   = str(uuid.uuid4())
    temp_file_path = f"temp_uploads/{secure_token}_{uploaded_file.filename}"

    with open(temp_file_path, "wb") as buffer:
        buffer.write(file_content)

    repository.create_initial_scan_record(database_session, secure_token, file_hash)

    background_tasks.add_task(
        service.execute_background_ai_scan,
        temp_file_path,
        secure_token,
        document_type,
        current_user.account_id if current_user else None,
        current_user.account_id if current_user else None,
        current_user.email_address if current_user else None,
        request.client.host if request.client else None,  
    )

    return schemas.ScanInitiationResponse(
        secure_scan_token=secure_token,
        processing_status="PROCESSING",
        message="Your document is safely uploaded and is currently being analyzed.",
    )


@document_router.get("/status/{scan_token}", response_model=schemas.ScanStatusReport)
def check_scan_status(
    scan_token: str,
    database_session: Session = Depends(get_database_session),
):
    scan_record = repository.fetch_scan_by_token(database_session, scan_token)
    if scan_record is None:
        raise HTTPException(status_code=404, detail="Scan token not found.")

    return schemas.ScanStatusReport(
        processing_status=scan_record.processing_status,
        extracted_ai_data=scan_record.extracted_ai_data,
        error_message=scan_record.error_message,
    )


@document_router.get("/verification/{scan_token}")
def get_verification_score_card(
    scan_token: str,
    database_session: Session = Depends(get_database_session),
):
    scan_record = repository.fetch_scan_by_token(database_session, scan_token)
    if scan_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No scan record found for token '{scan_token}'.",
        )

    extracted_data       = None
    confidence_breakdown = None
    model_used           = None
    verification_result  = None
    ai_recommendation    = None

    if scan_record.extracted_ai_data:
        try:
            payload              = json.loads(scan_record.extracted_ai_data)
            extracted_data       = payload.get("extracted_data")
            model_used           = payload.get("model_used")
            confidence_breakdown = payload.get("confidence_breakdown")
            verification_result  = payload.get("verification_result")
            ai_recommendation    = payload.get("ai_recommendation")
        except (json.JSONDecodeError, TypeError):
            extracted_data = None

    return {
        "scan_token":           scan_token,
        "document_type":        scan_record.document_type,
        "processing_status":    scan_record.processing_status,
        "confidence_score":     scan_record.confidence_score,
        "confidence_breakdown": confidence_breakdown,
        "extracted_data":       extracted_data,
        "model_used":           model_used,
        "verification_result":  verification_result,
        "ai_recommendation":    ai_recommendation,
        "error_message":        scan_record.error_message,
    }