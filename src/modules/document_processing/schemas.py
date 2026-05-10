# backend-v2/src/modules/document_processing/schemas.py
from pydantic import BaseModel
from typing import Optional, Any

class ScanInitiationResponse(BaseModel):
   
    secure_scan_token: str
    processing_status: str
    message: str

class ScanStatusReport(BaseModel):
    
    processing_status:  str
    extracted_ai_data:  Optional[str]   = None 
    confidence_score:   Optional[float] = None   
    error_message:      Optional[str]   = None

    class Config:
        from_attributes = True