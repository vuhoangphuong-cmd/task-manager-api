from sqlalchemy import Column, String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=True)
    progress_percent = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
