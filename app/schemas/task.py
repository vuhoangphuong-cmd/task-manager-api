from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    creator_user_id: Optional[str] = None
    owner_user_id: Optional[str] = None
    reviewer_user_id: Optional[str] = None
    priority: str = "medium"
    due_at: Optional[datetime] = None

class TaskProgressUpdate(BaseModel):
    actor_user_id: str
    progress_percent: int
    comment: Optional[str] = None

class TaskSubmit(BaseModel):
    actor_user_id: str
    result_summary: Optional[str] = None
    comment: Optional[str] = None

class TaskReview(BaseModel):
    actor_user_id: str
    decision: str
    review_note: Optional[str] = None
