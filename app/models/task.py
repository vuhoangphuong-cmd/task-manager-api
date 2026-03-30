from sqlalchemy import Column, String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_code = Column(String(50), unique=True, nullable=False)

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    creator_user_id = Column(UUID(as_uuid=True), nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), nullable=True)
    reviewer_user_id = Column(UUID(as_uuid=True), nullable=True)

    priority = Column(String(20), nullable=False, default="medium")
    status = Column(String(30), nullable=False, default="assigned")
    progress_percent = Column(Integer, nullable=False, default=0)

    due_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    result_summary = Column(Text, nullable=True)
    review_note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
