from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

router = APIRouter()

def normalize_role(role: str) -> str:
    r = (role or "").strip().lower()
    if r not in ["admin", "manager", "staff"]:
        return "staff"
    return r

@router.post("")
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        role=normalize_role(payload.role),
        department=payload.department,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

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

@router.get("")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "success": True,
        "data": [
            {
                "id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role,
                "department": u.department,
                "is_active": u.is_active,
            }
            for u in users
        ]
    }

@router.get("/{user_id}")
def get_user(user_id: str, db: Session = Depends(get_db)):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "success": True,
        "data": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "department": user.department,
            "is_active": user.is_active,
        }
    }

@router.put("/{user_id}")
def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db)):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        user.email = payload.email
    if payload.phone is not None:
        user.phone = payload.phone
    if payload.role is not None:
        user.role = normalize_role(payload.role)
    if payload.department is not None:
        user.department = payload.department
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

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
