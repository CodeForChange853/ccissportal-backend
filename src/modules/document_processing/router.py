import shutil
import uuid
import os
import json

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

    secure_token   = str(uuid.uuid4())
    temp_file_path = f"temp_uploads/{secure_token}_{uploaded_file.filename}"

    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(uploaded_file.file, buffer)

    repository.create_initial_scan_record(database_session, secure_token)

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