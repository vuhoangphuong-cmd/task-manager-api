from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    assignee: str = ""
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: Optional[str] = None
    status: Literal["todo", "in_progress", "done"] = "todo"


class TaskUpdate(BaseModel):
    title: str
    description: str = ""
    assignee: str = ""
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: Optional[str] = None
    status: Literal["todo", "in_progress", "done"] = "todo"


class StatusUpdate(BaseModel):
    status: Literal["todo", "in_progress", "done"]


class AISuggestIn(BaseModel):
    task_id: int


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    assignee: str
    priority: Literal["low", "medium", "high"]
    due_date: Optional[str] = None
    status: Literal["todo", "in_progress", "done"]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HistoryOut(BaseModel):
    id: int
    task_id: int
    action: str
    detail: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: EmailStr
    role: Literal["manager", "staff"]
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
