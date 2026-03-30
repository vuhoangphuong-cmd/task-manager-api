from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
import asyncio

from app.core.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.schemas.task import TaskCreate, TaskProgressUpdate, TaskSubmit, TaskReview
from app.ws_manager import manager

router = APIRouter()

def make_task_code() -> str:
    return f"T-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

def normalize_priority(priority: str) -> str:
    p = (priority or "").strip().lower()
    mapping = {
        "low": "low",
        "medium": "medium",
        "med": "medium",
        "high": "high",
        "thap": "low",
        "trung binh": "medium",
        "trung_binh": "medium",
        "cao": "high",
    }
    return mapping.get(p, "medium")

def compute_status(progress_percent: int) -> str:
    if progress_percent <= 0:
        return "assigned"
    if progress_percent >= 100:
        return "waiting_review"
    return "in_progress"

def get_user_or_400(db: Session, user_id: str | None):
    if not user_id:
        return None
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    user = db.query(User).filter(User.id == user_uuid, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found or inactive")
    return user

def require_role(user: User, allowed: list[str]):
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Permission denied")

def log_history(
    db: Session,
    task_id,
    action: str,
    old_status: str | None = None,
    new_status: str | None = None,
    progress_percent: int | None = None,
    comment: str | None = None,
):
    history = TaskHistory(
        task_id=task_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        progress_percent=progress_percent,
        comment=comment,
    )
    db.add(history)
    db.commit()

def task_brief(task: Task):
    return {
        "id": str(task.id),
        "task_code": task.task_code,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "progress_percent": task.progress_percent,
        "owner_user_id": str(task.owner_user_id) if task.owner_user_id else None,
        "reviewer_user_id": str(task.reviewer_user_id) if task.reviewer_user_id else None,
        "due_at": task.due_at.isoformat() if task.due_at else None,
    }

def push_event(event_type: str, task: Task):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast({
            "type": event_type,
            "task": task_brief(task)
        }))
    except RuntimeError:
        pass

@router.post("")
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    creator = get_user_or_400(db, payload.creator_user_id) if payload.creator_user_id else None
    owner = get_user_or_400(db, payload.owner_user_id) if payload.owner_user_id else None
    reviewer = get_user_or_400(db, payload.reviewer_user_id) if payload.reviewer_user_id else None

    if creator:
        require_role(creator, ["admin", "manager"])

    task = Task(
        task_code=make_task_code(),
        title=payload.title,
        description=payload.description,
        creator_user_id=creator.id if creator else None,
        owner_user_id=owner.id if owner else None,
        reviewer_user_id=reviewer.id if reviewer else None,
        priority=normalize_priority(payload.priority),
        due_at=payload.due_at,
        status="assigned",
        progress_percent=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    log_history(
        db=db,
        task_id=task.id,
        action="created",
        old_status=None,
        new_status="assigned",
        progress_percent=0,
        comment="Task created",
    )

    push_event("task_created", task)

    return {
        "success": True,
        "data": task_brief(task),
    }

@router.get("")
def list_tasks(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    owner_user_id: str | None = Query(default=None),
    reviewer_user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Task)

    if status:
        query = query.filter(Task.status == status)

    if priority:
        query = query.filter(Task.priority == normalize_priority(priority))

    if q:
        like = f"%{q}%"
        query = query.filter((Task.title.ilike(like)) | (Task.description.ilike(like)))

    if owner_user_id:
        try:
            owner_uuid = uuid.UUID(owner_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid owner_user_id format")
        query = query.filter(Task.owner_user_id == owner_uuid)

    if reviewer_user_id:
        try:
            reviewer_uuid = uuid.UUID(reviewer_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid reviewer_user_id format")
        query = query.filter(Task.reviewer_user_id == reviewer_uuid)

    if overdue:
        now = datetime.now(timezone.utc)
        query = query.filter(
            Task.due_at.isnot(None),
            Task.due_at < now,
            Task.status.notin_(["completed"])
        )

    tasks = query.order_by(Task.created_at.desc()).limit(100).all()

    return {
        "success": True,
        "data": [task_brief(t) for t in tasks],
    }

@router.get("/{task_id}")
def get_task_detail(task_id: str, db: Session = Depends(get_db)):
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    task = db.query(Task).filter(Task.id == task_uuid).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    history = (
        db.query(TaskHistory)
        .filter(TaskHistory.task_id == task_uuid)
        .order_by(TaskHistory.created_at.desc())
        .all()
    )

    return {
        "success": True,
        "data": {
            **task_brief(task),
            "description": task.description,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "result_summary": task.result_summary,
            "review_note": task.review_note,
            "creator_user_id": str(task.creator_user_id) if task.creator_user_id else None,
            "history": [
                {
                    "action": h.action,
                    "old_status": h.old_status,
                    "new_status": h.new_status,
                    "progress_percent": h.progress_percent,
                    "comment": h.comment,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
                for h in history
            ],
        },
    }

@router.post("/{task_id}/progress")
def update_progress(task_id: str, payload: TaskProgressUpdate, db: Session = Depends(get_db)):
    actor = get_user_or_400(db, payload.actor_user_id)

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    task = db.query(Task).filter(Task.id == task_uuid).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if actor and actor.role == "staff":
        if not task.owner_user_id or str(task.owner_user_id) != str(actor.id):
            raise HTTPException(status_code=403, detail="Staff can only update their own tasks")

    if task.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot update progress for a completed task")

    if payload.progress_percent < 0 or payload.progress_percent > 100:
        raise HTTPException(status_code=400, detail="progress_percent must be between 0 and 100")

    old_status = task.status

    if payload.progress_percent >= 100:
        task.progress_percent = 100
        task.status = "waiting_review"
        task.result_summary = task.result_summary or "Auto submit từ hệ thống"
        task.completed_at = None

        db.commit()
        db.refresh(task)

        log_history(
            db=db,
            task_id=task.id,
            action="submitted",
            old_status=old_status,
            new_status="waiting_review",
            progress_percent=100,
            comment="Auto submit khi đạt 100%",
        )
        push_event("task_submitted", task)
    else:
        task.progress_percent = payload.progress_percent
        task.status = compute_status(payload.progress_percent)
        task.completed_at = None

        db.commit()
        db.refresh(task)

        log_history(
            db=db,
            task_id=task.id,
            action="progress_update",
            old_status=old_status,
            new_status=task.status,
            progress_percent=payload.progress_percent,
            comment=payload.comment or "Update progress",
        )
        push_event("task_progress_updated", task)

    return {
        "success": True,
        "data": {
            "id": str(task.id),
            "task_code": task.task_code,
            "status": task.status,
            "progress_percent": task.progress_percent,
        },
    }

@router.post("/{task_id}/submit")
def submit_task(task_id: str, payload: TaskSubmit, db: Session = Depends(get_db)):
    actor = get_user_or_400(db, payload.actor_user_id)

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    task = db.query(Task).filter(Task.id == task_uuid).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if actor and actor.role == "staff":
        if not task.owner_user_id or str(task.owner_user_id) != str(actor.id):
            raise HTTPException(status_code=403, detail="Staff can only submit their own tasks")

    if task.status == "completed":
        raise HTTPException(status_code=400, detail="Completed task cannot be submitted again")
    if task.status == "waiting_review":
        raise HTTPException(status_code=400, detail="Task is already waiting for review")
    if task.progress_percent < 80:
        raise HTTPException(status_code=400, detail="Task must be at least 80% complete before submit")

    old_status = task.status
    task.result_summary = payload.result_summary
    task.progress_percent = 100
    task.status = "waiting_review"
    task.completed_at = None

    db.commit()
    db.refresh(task)

    log_history(
        db=db,
        task_id=task.id,
        action="submitted",
        old_status=old_status,
        new_status="waiting_review",
        progress_percent=100,
        comment=payload.comment or payload.result_summary,
    )
    push_event("task_submitted", task)

    return {
        "success": True,
        "data": {
            "id": str(task.id),
            "task_code": task.task_code,
            "status": task.status,
            "progress_percent": task.progress_percent,
        },
    }

@router.post("/{task_id}/review")
def review_task(task_id: str, payload: TaskReview, db: Session = Depends(get_db)):
    actor = get_user_or_400(db, payload.actor_user_id)
    if actor:
        require_role(actor, ["admin", "manager"])

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    task = db.query(Task).filter(Task.id == task_uuid).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.reviewer_user_id and actor and str(task.reviewer_user_id) != str(actor.id) and actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only assigned reviewer or admin can review this task")

    if task.status != "waiting_review":
        raise HTTPException(status_code=400, detail="Only tasks in waiting_review can be reviewed")

    decision = (payload.decision or "").strip().lower()
    if decision not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="decision must be approve or reject")

    old_status = task.status

    if decision == "approve":
        task.status = "completed"
        task.progress_percent = 100
        task.completed_at = datetime.now(timezone.utc)
        action = "review_approved"
        event_type = "task_approved"
    else:
        task.status = "in_progress"
        task.progress_percent = 80
        task.completed_at = None
        action = "review_rejected"
        event_type = "task_rejected"

    task.review_note = payload.review_note

    db.commit()
    db.refresh(task)

    log_history(
        db=db,
        task_id=task.id,
        action=action,
        old_status=old_status,
        new_status=task.status,
        progress_percent=task.progress_percent,
        comment=payload.review_note,
    )
    push_event(event_type, task)

    return {
        "success": True,
        "data": {
            "id": str(task.id),
            "task_code": task.task_code,
            "status": task.status,
            "progress_percent": task.progress_percent,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        },
    }
