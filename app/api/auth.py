from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest

router = APIRouter()

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email, User.is_active == True)
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found or inactive")

    return {
        "success": True,
        "data": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "department": user.department,
            "is_active": user.is_active,
        }
    }
