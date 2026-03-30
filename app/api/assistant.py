from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
import re
import dateparser

from app.core.database import get_db
from app.models.task import Task
from app.models.task_history import TaskHistory
from app.models.user import User
from app.schemas.assistant import AssistantCommandRequest

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
        "ưu tiên thấp": "low",
        "uu tien thap": "low",
        "ưu tiên trung bình": "medium",
        "uu tien trung binh": "medium",
        "ưu tiên cao": "high",
        "uu tien cao": "high",
    }
    return mapping.get(p, "medium")

def compute_status(progress_percent: int) -> str:
    if progress_percent <= 0:
        return "assigned"
    if progress_percent >= 100:
        return "waiting_review"
    return "in_progress"

def get_user_or_400(db: Session, user_id: str):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    user = db.query(User).filter(User.id == user_uuid, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found or inactive")
    return user

def find_user_by_name(db: Session, raw_name: str):
    if not raw_name:
        return None
    q = raw_name.strip().lower()
    users = db.query(User).filter(User.is_active == True).all()

    # exact
    for u in users:
        if (u.full_name or "").strip().lower() == q:
            return u
    # contains both ways
    for u in users:
        full = (u.full_name or "").strip().lower()
        if q in full or full in q:
            return u
    return None

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

def task_to_brief(task: Task):
    return {
        "id": str(task.id),
        "task_code": task.task_code,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "progress_percent": task.progress_percent,
        "due_at": task.due_at.isoformat() if task.due_at else None,
    }

def parse_due_date(text: str):
    # ưu tiên ISO rõ ràng
    iso_match = re.search(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)', text)
    if iso_match:
        raw = iso_match.group(1).replace(" ", "T")
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            pass

    # hỗ trợ dd/mm/yyyy hh:mm hoặc dd/mm hh:mm
    common_match = re.search(r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?(?:\s+\d{1,2}:\d{2})?)', text)
    if common_match:
        parsed = dateparser.parse(
            common_match.group(1),
            languages=["vi", "en"],
            settings={
                "DATE_ORDER": "DMY",
                "PREFER_DAY_OF_MONTH": "first",
                "TIMEZONE": "Asia/Bangkok",
                "RETURN_AS_TIMEZONE_AWARE": True,
            },
        )
        if parsed:
            return parsed

    # parse natural language tiếng Việt / English
    parsed = dateparser.parse(
        text,
        languages=["vi", "en"],
        settings={
            "DATE_ORDER": "DMY",
            "PREFER_DAY_OF_MONTH": "first",
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Asia/Bangkok",
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    return parsed

def extract_priority(text: str):
    text_l = text.lower()
    if "ưu tiên cao" in text_l or "uu tien cao" in text_l or "priority high" in text_l:
        return "high"
    if "ưu tiên thấp" in text_l or "uu tien thap" in text_l or "priority low" in text_l:
        return "low"
    return "medium"

def extract_create_task_fields(db: Session, text: str):
    text_clean = " ".join(text.strip().split())
    text_l = text_clean.lower()

    owner = None
    reviewer = None

    owner_patterns = [
        r"giao cho\s+(.+?)\s+duyệt bởi",
        r"giao cho\s+(.+?)\s+duyet boi",
        r"owner\s*=\s*(.+?)(?:;|$)",
        r"thực hiện bởi\s+(.+?)\s+duyệt",
        r"thuc hien boi\s+(.+?)\s+duyet",
    ]
    reviewer_patterns = [
        r"duyệt bởi\s+(.+?)(?:\s+hạn|\s+han|\s+ưu tiên|\s+uu tien|$)",
        r"duyet boi\s+(.+?)(?:\s+han|\s+ưu tiên|\s+uu tien|$)",
        r"reviewer\s*=\s*(.+?)(?:;|$)",
    ]

    for p in owner_patterns:
        m = re.search(p, text_clean, flags=re.IGNORECASE)
        if m:
            owner = find_user_by_name(db, m.group(1).strip())
            if owner:
                break

    for p in reviewer_patterns:
        m = re.search(p, text_clean, flags=re.IGNORECASE)
        if m:
            reviewer = find_user_by_name(db, m.group(1).strip())
            if reviewer:
                break

    due = None
    due_patterns = [
        r"hạn\s+(.+?)(?:\s+ưu tiên|\s+uu tien|$)",
        r"han\s+(.+?)(?:\s+uu tien|$)",
        r"due\s*=\s*(.+?)(?:;|$)",
    ]
    for p in due_patterns:
        m = re.search(p, text_clean, flags=re.IGNORECASE)
        if m:
            due = parse_due_date(m.group(1).strip())
            if due:
                break

    priority = extract_priority(text_clean)

    # lấy title bằng cách cắt bỏ tiền tố "tạo task"
    title = re.sub(r"^(tạo|tao)\s+task\s*", "", text_clean, flags=re.IGNORECASE).strip()

    # cắt các phần meta để title gọn hơn
    title = re.split(r"\s+giao cho\s+|\s+owner\s*=|\s+thực hiện bởi\s+|\s+thuc hien boi\s+", title, flags=re.IGNORECASE)[0].strip(" :;-")

    return {
        "title": title,
        "owner": owner,
        "reviewer": reviewer,
        "due_at": due,
        "priority": priority,
    }

@router.post("/command")
def assistant_command(payload: AssistantCommandRequest, db: Session = Depends(get_db)):
    actor = get_user_or_400(db, payload.actor_user_id)
    text = (payload.message or "").strip()
    text_l = text.lower()
    now = datetime.now(timezone.utc)

    if text_l in ["dashboard của tôi", "dashboard cua toi", "tong quan cua toi", "tổng quan của tôi"]:
        assigned_to_me = db.query(Task).filter(Task.owner_user_id == actor.id).count()
        assigned_open = db.query(Task).filter(Task.owner_user_id == actor.id, Task.status == "assigned").count()
        in_progress_me = db.query(Task).filter(Task.owner_user_id == actor.id, Task.status == "in_progress").count()
        waiting_review_me = db.query(Task).filter(Task.owner_user_id == actor.id, Task.status == "waiting_review").count()
        completed_me = db.query(Task).filter(Task.owner_user_id == actor.id, Task.status == "completed").count()
        overdue_me = db.query(Task).filter(
            Task.owner_user_id == actor.id,
            Task.due_at.isnot(None),
            Task.due_at < now,
            Task.status.notin_(["completed"])
        ).count()
        pending_review_for_me = db.query(Task).filter(
            Task.reviewer_user_id == actor.id,
            Task.status == "waiting_review"
        ).count()

        return {
            "success": True,
            "reply": f"{actor.full_name}: assigned {assigned_to_me}, đang làm {in_progress_me}, chờ duyệt {waiting_review_me}, hoàn thành {completed_me}, quá hạn {overdue_me}, cần duyệt {pending_review_for_me}.",
            "data": {
                "assigned_to_me": assigned_to_me,
                "assigned_open": assigned_open,
                "in_progress_me": in_progress_me,
                "waiting_review_me": waiting_review_me,
                "completed_me": completed_me,
                "overdue_me": overdue_me,
                "pending_review_for_me": pending_review_for_me,
            }
        }

    if text_l in ["việc của tôi", "viec cua toi", "task của tôi", "task cua toi"]:
        my_tasks = db.query(Task).filter(Task.owner_user_id == actor.id).order_by(Task.created_at.desc()).limit(100).all()
        return {
            "success": True,
            "reply": f"{actor.full_name} hiện có {len(my_tasks)} task.",
            "data": [task_to_brief(t) for t in my_tasks]
        }

    if text_l in ["việc cần duyệt của tôi", "viec can duyet cua toi", "queue duyệt của tôi", "queue duyet cua toi"]:
        review_tasks = db.query(Task).filter(
            Task.reviewer_user_id == actor.id,
            Task.status == "waiting_review"
        ).order_by(Task.created_at.desc()).all()
        return {
            "success": True,
            "reply": f"{actor.full_name} hiện có {len(review_tasks)} task chờ duyệt.",
            "data": [task_to_brief(t) for t in review_tasks]
        }

    # smart create task
    if text_l.startswith("tạo task") or text_l.startswith("tao task"):
        if actor.role not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="Permission denied")

        parsed = extract_create_task_fields(db, text)
        if not parsed["title"]:
            raise HTTPException(status_code=400, detail="Không nhận diện được tiêu đề task")
        if not parsed["owner"]:
            raise HTTPException(status_code=400, detail="Không nhận diện được người thực hiện")
        if not parsed["reviewer"]:
            raise HTTPException(status_code=400, detail="Không nhận diện được người duyệt")
        if not parsed["due_at"]:
            raise HTTPException(status_code=400, detail="Không nhận diện được hạn hoàn thành")

        task = Task(
            task_code=make_task_code(),
            title=parsed["title"],
            description="Tạo từ AI Assistant",
            creator_user_id=actor.id,
            owner_user_id=parsed["owner"].id,
            reviewer_user_id=parsed["reviewer"].id,
            priority=parsed["priority"],
            due_at=parsed["due_at"],
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
            comment="Task created by smart parser",
        )

        return {
            "success": True,
            "reply": f"Đã tạo task {task.task_code} - {task.title}, giao cho {parsed['owner'].full_name}, duyệt bởi {parsed['reviewer'].full_name}.",
            "data": task_to_brief(task),
        }

    m = re.match(r"^(cập nhật|cap nhat)\s+task\s+([0-9a-fA-F\-]+)\s+(lên|len)\s+(\d{1,3})%$", text_l)
    if m:
        task_id = m.group(2)
        progress_percent = int(m.group(4))

        try:
            task_uuid = uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task_id format")

        task = db.query(Task).filter(Task.id == task_uuid).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if actor.role == "staff" and (not task.owner_user_id or str(task.owner_user_id) != str(actor.id)):
            raise HTTPException(status_code=403, detail="Staff can only update their own tasks")

        if task.status == "completed":
            raise HTTPException(status_code=400, detail="Cannot update progress for a completed task")

        if progress_percent < 0 or progress_percent > 100:
            raise HTTPException(status_code=400, detail="progress_percent must be between 0 and 100")

        old_status = task.status
        task.progress_percent = progress_percent
        task.status = compute_status(progress_percent)
        if task.status != "completed":
            task.completed_at = None

        db.commit()
        db.refresh(task)

        log_history(
            db=db,
            task_id=task.id,
            action="progress_update",
            old_status=old_status,
            new_status=task.status,
            progress_percent=progress_percent,
            comment="Update từ trợ lý AI",
        )

        return {
            "success": True,
            "reply": f"Đã cập nhật {task.task_code} lên {progress_percent}%.",
            "data": task_to_brief(task),
        }

    m = re.match(r"^submit\s+task\s+([0-9a-fA-F\-]+)\s*:\s*(.+)$", text, re.IGNORECASE)
    if m:
        task_id = m.group(1)
        result_summary = m.group(2).strip()

        try:
            task_uuid = uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task_id format")

        task = db.query(Task).filter(Task.id == task_uuid).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if actor.role == "staff" and (not task.owner_user_id or str(task.owner_user_id) != str(actor.id)):
            raise HTTPException(status_code=403, detail="Staff can only submit their own tasks")

        if task.status == "completed":
            raise HTTPException(status_code=400, detail="Completed task cannot be submitted again")
        if task.status == "waiting_review":
            raise HTTPException(status_code=400, detail="Task is already waiting for review")
        if task.progress_percent < 80:
            raise HTTPException(status_code=400, detail="Task must be at least 80% complete before submit")

        old_status = task.status
        task.result_summary = result_summary
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
            comment=result_summary,
        )

        return {
            "success": True,
            "reply": f"Đã nộp task {task.task_code} để duyệt.",
            "data": task_to_brief(task),
        }

    m = re.match(r"^(duyệt|duyet)\s+task\s+([0-9a-fA-F\-]+)\s*:\s*(.+)$", text, re.IGNORECASE)
    if m:
        if actor.role not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="Permission denied")

        task_id = m.group(2)
        review_note = m.group(3).strip()

        try:
            task_uuid = uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task_id format")

        task = db.query(Task).filter(Task.id == task_uuid).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.reviewer_user_id and str(task.reviewer_user_id) != str(actor.id) and actor.role != "admin":
            raise HTTPException(status_code=403, detail="Only assigned reviewer or admin can review this task")
        if task.status != "waiting_review":
            raise HTTPException(status_code=400, detail="Only tasks in waiting_review can be reviewed")

        old_status = task.status
        task.status = "completed"
        task.progress_percent = 100
        task.completed_at = datetime.now(timezone.utc)
        task.review_note = review_note

        db.commit()
        db.refresh(task)

        log_history(
            db=db,
            task_id=task.id,
            action="review_approved",
            old_status=old_status,
            new_status=task.status,
            progress_percent=task.progress_percent,
            comment=review_note,
        )

        return {
            "success": True,
            "reply": f"Đã duyệt task {task.task_code}.",
            "data": task_to_brief(task),
        }

    m = re.match(r"^(từ chối|tu choi)\s+task\s+([0-9a-fA-F\-]+)\s*:\s*(.+)$", text, re.IGNORECASE)
    if m:
        if actor.role not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="Permission denied")

        task_id = m.group(2)
        review_note = m.group(3).strip()

        try:
            task_uuid = uuid.UUID(task_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task_id format")

        task = db.query(Task).filter(Task.id == task_uuid).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.reviewer_user_id and str(task.reviewer_user_id) != str(actor.id) and actor.role != "admin":
            raise HTTPException(status_code=403, detail="Only assigned reviewer or admin can review this task")
        if task.status != "waiting_review":
            raise HTTPException(status_code=400, detail="Only tasks in waiting_review can be reviewed")

        old_status = task.status
        task.status = "in_progress"
        task.progress_percent = 80
        task.completed_at = None
        task.review_note = review_note

        db.commit()
        db.refresh(task)

        log_history(
            db=db,
            task_id=task.id,
            action="review_rejected",
            old_status=old_status,
            new_status=task.status,
            progress_percent=task.progress_percent,
            comment=review_note,
        )

        return {
            "success": True,
            "reply": f"Đã từ chối task {task.task_code}.",
            "data": task_to_brief(task),
        }

    raise HTTPException(
        status_code=400,
        detail="Lệnh chưa được hỗ trợ. Ví dụ: 'dashboard của tôi', 'việc của tôi', 'việc cần duyệt của tôi', 'tạo task chuẩn bị slide hội nghị giao cho Staff Test duyệt bởi Manager Test hạn thứ 2 tuần sau ưu tiên cao', 'cập nhật task <uuid> lên 70%', 'submit task <uuid>: ...', 'duyệt task <uuid>: ...', 'từ chối task <uuid>: ...'"
    )
