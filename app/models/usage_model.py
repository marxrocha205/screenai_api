# app/models/usage_model.py

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    action = Column(String)
    cost = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())