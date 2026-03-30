from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "tasks_data.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_db() -> dict:
    if not DATA_FILE.exists():
        return {"tasks": [], "history": [], "next_task_id": 1, "next_history_id": 1}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": [], "history": [], "next_task_id": 1, "next_history_id": 1}


def save_db(db: dict) -> None:
    DATA_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


db = load_db()


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

app = FastAPI(title="Task Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def add_history(task_id: int, action: str, detail: str) -> None:
    history_item = {
        "id": db["next_history_id"],
        "task_id": task_id,
        "action": action,
        "detail": detail,
        "created_at": now_iso(),
    }
    db["next_history_id"] += 1
    db["history"].append(history_item)
    save_db(db)


def get_task_or_404(task_id: int) -> dict:
    for task in db["tasks"]:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks() -> List[dict]:
    return db["tasks"]


@app.post("/tasks")
async def create_task(payload: TaskCreate) -> dict:
    task = {
        "id": db["next_task_id"],
        "title": payload.title,
        "description": payload.description,
        "assignee": payload.assignee,
        "priority": payload.priority,
        "due_date": payload.due_date,
        "status": payload.status,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    db["next_task_id"] += 1
    db["tasks"].append(task)
    save_db(db)

    add_history(
        task["id"],
        "Tạo công việc",
        f'Tạo công việc "{task["title"]}" với trạng thái {task["status"]}',
    )

    await manager.broadcast_json(
        {
            "type": "task_created",
            "task_id": task["id"],
            "title": task["title"],
            "timestamp": now_iso(),
        }
    )

    return task


@app.get("/tasks/{task_id}")
def get_task(task_id: int) -> dict:
    return get_task_or_404(task_id)


@app.put("/tasks/{task_id}")
async def update_task(task_id: int, payload: TaskUpdate) -> dict:
    task = get_task_or_404(task_id)

    task["title"] = payload.title
    task["description"] = payload.description
    task["assignee"] = payload.assignee
    task["priority"] = payload.priority
    task["due_date"] = payload.due_date
    task["status"] = payload.status
    task["updated_at"] = now_iso()
    save_db(db)

    add_history(
        task_id,
        "Cập nhật công việc",
        f'Cập nhật công việc "{task["title"]}"',
    )

    await manager.broadcast_json(
        {
            "type": "task_updated",
            "task_id": task_id,
            "title": task["title"],
            "timestamp": now_iso(),
        }
    )

    return task


@app.patch("/tasks/{task_id}/status")
async def update_task_status(task_id: int, payload: StatusUpdate) -> dict:
    task = get_task_or_404(task_id)
    old_status = task["status"]
    task["status"] = payload.status
    task["updated_at"] = now_iso()
    save_db(db)

    add_history(
        task_id,
        "Cập nhật trạng thái",
        f'Trạng thái từ "{old_status}" sang "{payload.status}"',
    )

    await manager.broadcast_json(
        {
            "type": "task_status_updated",
            "task_id": task_id,
            "title": task["title"],
            "status": payload.status,
            "timestamp": now_iso(),
        }
    )

    return task


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int) -> dict:
    task = get_task_or_404(task_id)
    db["tasks"] = [t for t in db["tasks"] if t["id"] != task_id]
    db["history"] = [h for h in db["history"] if h["task_id"] != task_id]
    save_db(db)

    await manager.broadcast_json(
        {
            "type": "task_deleted",
            "task_id": task_id,
            "title": task["title"],
            "timestamp": now_iso(),
        }
    )

    return {"ok": True}


@app.get("/tasks/{task_id}/history")
def get_task_history(task_id: int) -> List[dict]:
    get_task_or_404(task_id)
    return [h for h in db["history"] if h["task_id"] == task_id]


@app.post("/ai/suggest")
def ai_suggest(payload: AISuggestIn) -> dict:
    task = get_task_or_404(payload.task_id)

    suggestions = [
        "Rà soát lại mô tả công việc để cụ thể hóa đầu ra cần bàn giao.",
        "Kiểm tra hạn hoàn thành và bổ sung mốc trung gian nếu công việc kéo dài.",
        "Xác nhận người phụ trách và người giao việc để tránh chồng chéo.",
    ]

    if task["status"] == "todo":
        summary = "AI gợi ý: Công việc đang ở trạng thái chưa thực hiện, nên làm rõ mục tiêu và kế hoạch triển khai."
    elif task["status"] == "in_progress":
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
