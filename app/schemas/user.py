from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "staff"
    department: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None
