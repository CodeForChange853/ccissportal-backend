# backend-v2/src/modules/auth/models.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from src.core.database_setup import Base


class UserAccount(Base):
   
    __tablename__ = "user_accounts"


    account_id = Column(Integer, primary_key=True, index=True)
    email_address = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    account_role = Column(String(50), nullable=False)
    is_active_account = Column(Boolean, default=True)
    account_created_at = Column(DateTime(timezone=True), server_default=func.now())