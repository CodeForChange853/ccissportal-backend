# backend-v2/src/modules/document_processing/repository.py

from sqlalchemy.orm import Session
from .models import DocumentScanResult

def create_initial_scan_record(database_session: Session, new_token: str) -> DocumentScanResult:
    new_record = DocumentScanResult(secure_scan_token=new_token, processing_status="PROCESSING")
    database_session.add(new_record)
    database_session.commit()
    return new_record

def fetch_scan_by_token(database_session: Session, token: str) -> DocumentScanResult | None:
    return database_session.query(DocumentScanResult).filter(
        DocumentScanResult.secure_scan_token == token
    ).first()

def update_scan_completion(
    database_session: Session,
    token: str,
    extracted_data: str = None,
    error_msg: str = None,
    confidence_score: float = None,
    document_type: str = None,          # "ID" or "COR"
    status: str = None,
):
    scan_record = fetch_scan_by_token(database_session, token)
    if scan_record:
        if error_msg:
            scan_record.processing_status = status or "FAILED"
            scan_record.error_message     = error_msg
        else:
            scan_record.processing_status = "COMPLETED"
            scan_record.extracted_ai_data = extracted_data
            if confidence_score is not None:
                scan_record.confidence_score = confidence_score
            if document_type is not None:
                scan_record.document_type = document_type
        database_session.commit()