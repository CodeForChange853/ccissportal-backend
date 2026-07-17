# backend-v2/src/modules/auth/models.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from src.core.database_setup import Base


class UserAccount(Base):
   
    __tablename__ = "user_accounts"


    account_id = Column(Integer, primary_key=True, index=True)
    email_address = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    account_role = Column(String(50), nullable=False)
    is_active_account = Column(Boolean, default=True)
    violation_count = Column(Integer, default=0) # Track harassment/explicit content strikes
    account_created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Wall of Shame fields
    last_violation_at = Column(DateTime(timezone=True), nullable=True)
    violation_log = Column(JSON, nullable=True)  # [{offense, detected_at, keywords}]
    removed_from_wall_at = Column(DateTime(timezone=True), nullable=True)  # Set by admin on reform