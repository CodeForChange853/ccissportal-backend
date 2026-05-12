# backend-v2/src/modules/document_processing/models.py

from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.sql import func
from src.core.database_setup import Base

class DocumentScanResult(Base):

    __tablename__ = "document_scan_results"

    scan_id = Column(Integer, primary_key=True, index=True)
    
    secure_scan_token = Column(String(255), unique=True, index=True, nullable=False)
    
    processing_status = Column(String(50), default="PROCESSING", index=True)
    
    extracted_ai_data = Column(Text, nullable=True) 
    
    error_message = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    document_type = Column(String(10), nullable=True)
    file_hash = Column(String(64), index=True, nullable=True) # Unique document fingerprint
    date_scanned = Column(DateTime(timezone=True), server_default=func.now())