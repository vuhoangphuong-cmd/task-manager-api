from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.models.task import Task
from app.models.user import User

router = APIRouter()

def get_user_or_404(db: Session, user_id: str):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    user = db.query(User).filter(User.id == user_uuid, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found or inactive")
    return user, user_uuid

@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    total = db.query(Task).count()
    assigned = db.query(Task).filter(Task.status == "assigned").count()
    in_progress = db.query(Task).filter(Task.status == "in_progress").count()
    waiting_review = db.query(Task).filter(Task.status == "waiting_review").count()
    completed = db.query(Task).filter(Task.status == "completed").count()

    overdue = db.query(Task).filter(
        Task.due_at.isnot(None),
        Task.due_at < now,
        Task.status.notin_(["completed"])
    ).count()

    return {
        "success": True,
        "data": {
            "total_tasks": total,
            "assigned": assigned,
            "in_progress": in_progress,
            "waiting_review": waiting_review,
            "completed": completed,
            "overdue": overdue,
        },
    }

@router.get("/summary-by-user/{user_id}")
def dashboard_summary_by_user(user_id: str, db: Session = Depends(get_db)):
    user, user_uuid = get_user_or_404(db, user_id)
    now = datetime.now(timezone.utc)

    assigned_to_me = db.query(Task).filter(Task.owner_user_id == user_uuid).count()
    assigned_open = db.query(Task).filter(
        Task.owner_user_id == user_uuid,
        Task.status == "assigned"
    ).count()
    in_progress_me = db.query(Task).filter(
        Task.owner_user_id == user_uuid,
        Task.status == "in_progress"
    ).count()
    waiting_review_me = db.query(Task).filter(
        Task.owner_user_id == user_uuid,
        Task.status == "waiting_review"
    ).count()
    completed_me = db.query(Task).filter(
        Task.owner_user_id == user_uuid,
        Task.status == "completed"
    ).count()

    overdue_me = db.query(Task).filter(
        Task.owner_user_id == user_uuid,
        Task.due_at.isnot(None),
        Task.due_at < now,
        Task.status.notin_(["completed"])
    ).count()

    created_by_me = db.query(Task).filter(Task.creator_user_id == user_uuid).count()
    pending_review_for_me = db.query(Task).filter(
        Task.reviewer_user_id == user_uuid,
        Task.status == "waiting_review"
    ).count()

    return {
        "success": True,
        "data": {
            "user": {
                "id": str(user.id),
                "full_name": user.full_name,
                "role": user.role,
                "department": user.department,
            },
            "assigned_to_me": assigned_to_me,
            "assigned_open": assigned_open,
            "in_progress_me": in_progress_me,
            "waiting_review_me": waiting_review_me,
            "completed_me": completed_me,
            "overdue_me": overdue_me,
            "created_by_me": created_by_me,
            "pending_review_for_me": pending_review_for_me,
        },
    }

@router.get("/my-work/{user_id}")
def dashboard_my_work(user_id: str, db: Session = Depends(get_db)):
    user, user_uuid = get_user_or_404(db, user_id)
    now = datetime.now(timezone.utc)

    my_tasks = db.query(Task).filter(Task.owner_user_id == user_uuid).order_by(Task.created_at.desc()).limit(100).all()
    my_reviews = db.query(Task).filter(Task.reviewer_user_id == user_uuid).order_by(Task.created_at.desc()).limit(100).all()

    overdue_tasks = db.query(Task).filter(
        Task.owner_user_id == user_uuid,
        Task.due_at.isnot(None),
        Task.due_at < now,
        Task.status.notin_(["completed"])
    ).order_by(Task.due_at.asc()).all()

    return {
        "success": True,
        "data": {
            "user": {
                "id": str(user.id),
                "full_name": user.full_name,
                "role": user.role,
                "department": user.department,
            },
            "my_tasks": [
                {
                    "id": str(t.id),
                    "task_code": t.task_code,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "progress_percent": t.progress_percent,
                    "due_at": t.due_at.isoformat() if t.due_at else None,
                }
                for t in my_tasks
            ],
            "my_review_queue": [
                {
                    "id": str(t.id),
                    "task_code": t.task_code,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "progress_percent": t.progress_percent,
                    "due_at": t.due_at.isoformat() if t.due_at else None,
                }
                for t in my_reviews if t.status == "waiting_review"
            ],
            "my_overdue_tasks": [
                {
                    "id": str(t.id),
                    "task_code": t.task_code,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "progress_percent": t.progress_percent,
                    "due_at": t.due_at.isoformat() if t.due_at else None,
                }
                for t in overdue_tasks
            ],
        },
    }
