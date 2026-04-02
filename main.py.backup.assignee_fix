from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Task, TaskHistory, User
from app.schemas import (
    AISuggestIn,
    HistoryOut,
    LoginEmailIn,
    RegisterIn,
    StatusUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    UserOut,
)
from app.security import create_access_token, decode_access_token, get_password_hash, verify_password
from app.settings import get_settings

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login-email")


def now_utc() -> datetime:
    return datetime.utcnow()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, message: dict) -> None:
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def add_history(db: Session, task_id: int, action: str, detail: str) -> TaskHistory:
    history_item = TaskHistory(
        task_id=task_id,
        action=action,
        detail=detail,
        created_at=now_utc(),
    )
    db.add(history_item)
    db.commit()
    db.refresh(history_item)
    return history_item


def get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def authenticate_user_by_email(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không xác thực được người dùng",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if not email:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")
    return user


def is_manager(user: User) -> bool:
    return user.role in {"truong_phong", "pho_truong_phong"}


def matches_task_assignee(user: User, task: Task) -> bool:
    assignee = (task.assignee or "").strip().lower()
    candidates = {
        (user.email or "").strip().lower(),
        (user.full_name or "").strip().lower(),
    }
    return assignee in candidates


def require_task_access(user: User, task: Task) -> None:
    if is_manager(user):
        return
    if not matches_task_assignee(user, task):
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập công việc này")


def require_manager(user: User) -> None:
    if not is_manager(user):
        raise HTTPException(status_code=403, detail="Chỉ trưởng/phó phòng được phép thực hiện thao tác này")


def normalized_staff_assignee(user: User) -> str:
    return (user.full_name or user.email or "").strip()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        return {"status": "error", "db": str(e)}


@app.post("/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")

    user = User(
        username=payload.email,
        full_name=payload.full_name,
        email=payload.email,
        role=payload.role,
        hashed_password=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=user.email)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        },
    }


@app.post("/auth/login-email")
def login_email(payload: LoginEmailIn, db: Session = Depends(get_db)):
    user = authenticate_user_by_email(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=user.email)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        },
    }


@app.get("/auth/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return current_user


@app.get("/tasks", response_model=List[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Task]:
    if is_manager(current_user):
        return db.query(Task).order_by(Task.id.asc()).all()

    candidates = [
        current_user.email.strip(),
        (current_user.full_name or "").strip(),
    ]
    candidates = [x for x in candidates if x]

    return (
        db.query(Task)
        .filter(or_(*[Task.assignee == value for value in candidates]))
        .order_by(Task.id.asc())
        .all()
    )


@app.post("/tasks", response_model=TaskOut)
async def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    assignee = payload.assignee
    if not is_manager(current_user):
        assignee = normalized_staff_assignee(current_user)

    task = Task(
        title=payload.title,
        description=payload.description,
        assignee=assignee,
        priority=payload.priority,
        due_date=payload.due_date,
        status=payload.status,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    add_history(
        db,
        task.id,
        "Tạo công việc",
        f'Tạo công việc "{task.title}" với trạng thái {task.status}',
    )

    await manager.broadcast_json(
        {
            "type": "task_created",
            "task_id": task.id,
            "title": task.title,
            "timestamp": now_utc().isoformat(timespec="seconds"),
        }
    )

    return task


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = get_task_or_404(db, task_id)
    require_task_access(current_user, task)
    return task


@app.put("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = get_task_or_404(db, task_id)
    require_task_access(current_user, task)

    task.title = payload.title
    task.description = payload.description
    task.priority = payload.priority
    task.due_date = payload.due_date
    task.status = payload.status
    task.updated_at = now_utc()

    if is_manager(current_user):
        task.assignee = payload.assignee
    else:
        task.assignee = normalized_staff_assignee(current_user)

    db.commit()
    db.refresh(task)

    add_history(
        db,
        task_id,
        "Cập nhật công việc",
        f'Cập nhật công việc "{task.title}"',
    )

    await manager.broadcast_json(
        {
            "type": "task_updated",
            "task_id": task_id,
            "title": task.title,
            "timestamp": now_utc().isoformat(timespec="seconds"),
        }
    )

    return task


@app.patch("/tasks/{task_id}/status", response_model=TaskOut)
async def update_task_status(
    task_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = get_task_or_404(db, task_id)
    require_task_access(current_user, task)

    old_status = task.status
    task.status = payload.status
    task.updated_at = now_utc()

    db.commit()
    db.refresh(task)

    add_history(
        db,
        task_id,
        "Cập nhật trạng thái",
        f'Trạng thái từ "{old_status}" sang "{payload.status}"',
    )

    await manager.broadcast_json(
        {
            "type": "task_status_updated",
            "task_id": task_id,
            "title": task.title,
            "status": payload.status,
            "timestamp": now_utc().isoformat(timespec="seconds"),
        }
    )

    return task


@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_manager(current_user)

    task = get_task_or_404(db, task_id)
    title = task.title

    db.delete(task)
    db.commit()

    await manager.broadcast_json(
        {
            "type": "task_deleted",
            "task_id": task_id,
            "title": title,
            "timestamp": now_utc().isoformat(timespec="seconds"),
        }
    )

    return {"ok": True}


@app.get("/tasks/{task_id}/history", response_model=List[HistoryOut])
def get_task_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TaskHistory]:
    task = get_task_or_404(db, task_id)
    require_task_access(current_user, task)

    return (
        db.query(TaskHistory)
        .filter(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.id.asc())
        .all()
    )


@app.post("/ai/suggest")
def ai_suggest(
    payload: AISuggestIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = get_task_or_404(db, payload.task_id)
    require_task_access(current_user, task)

    suggestions = [
        "Rà soát lại mô tả công việc để cụ thể hóa đầu ra cần bàn giao.",
        "Kiểm tra hạn hoàn thành và bổ sung mốc trung gian nếu công việc kéo dài.",
        "Xác nhận người phụ trách và người giao việc để tránh chồng chéo.",
    ]

    if task.status == "todo":
        summary = "AI gợi ý: Công việc đang ở trạng thái chưa thực hiện, nên làm rõ mục tiêu và kế hoạch triển khai."
    elif task.status == "in_progress":
        summary = "AI gợi ý: Công việc đang được triển khai, nên cập nhật tiến độ và các vướng mắc chính."
    else:
        summary = "AI gợi ý: Công việc đã hoàn thành, nên chuẩn hóa nội dung bàn giao và tổng kết kết quả."

    return {
        "summary": summary,
        "suggestions": suggestions,
    }


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
