from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.models import Task, TaskHistory
from app.schemas import AISuggestIn, HistoryOut, StatusUpdate, TaskCreate, TaskOut, TaskUpdate
from app.settings import get_settings

settings = get_settings()


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


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


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


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/tasks", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db)) -> List[Task]:
    return db.query(Task).order_by(Task.id.asc()).all()


@app.post("/tasks", response_model=TaskOut)
async def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
    task = Task(
        title=payload.title,
        description=payload.description,
        assignee=payload.assignee,
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
def get_task(task_id: int, db: Session = Depends(get_db)) -> Task:
    return get_task_or_404(db, task_id)


@app.put("/tasks/{task_id}", response_model=TaskOut)
async def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)) -> Task:
    task = get_task_or_404(db, task_id)

    task.title = payload.title
    task.description = payload.description
    task.assignee = payload.assignee
    task.priority = payload.priority
    task.due_date = payload.due_date
    task.status = payload.status
    task.updated_at = now_utc()

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
async def update_task_status(task_id: int, payload: StatusUpdate, db: Session = Depends(get_db)) -> Task:
    task = get_task_or_404(db, task_id)
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
async def delete_task(task_id: int, db: Session = Depends(get_db)) -> dict:
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
def get_task_history(task_id: int, db: Session = Depends(get_db)) -> List[TaskHistory]:
    get_task_or_404(db, task_id)
    return (
        db.query(TaskHistory)
        .filter(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.id.asc())
        .all()
    )


@app.post("/ai/suggest")
def ai_suggest(payload: AISuggestIn, db: Session = Depends(get_db)) -> dict:
    task = get_task_or_404(db, payload.task_id)

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
