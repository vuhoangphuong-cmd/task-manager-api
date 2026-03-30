from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

app = FastAPI(title="Task Manager API Realtime + AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    assignee: Optional[str] = ""
    status: Optional[str] = "todo"
    priority: Optional[str] = "medium"
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None


class TaskStatusUpdate(BaseModel):
    status: str


class AIRequest(BaseModel):
    task_id: int


class Task(BaseModel):
    id: int
    title: str
    description: str = ""
    assignee: str = ""
    status: str = "todo"
    priority: str = "medium"
    due_date: Optional[str] = None
    created_at: str
    updated_at: str


class TaskHistoryItem(BaseModel):
    id: int
    task_id: int
    action: str
    detail: str
    created_at: str


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


tasks_db: Dict[int, Task] = {
    1: Task(
        id=1,
        title="Soạn báo cáo tuần",
        description="Tổng hợp số liệu hoạt động tuần",
        assignee="Phuong",
        status="todo",
        priority="high",
        due_date=(datetime.now() + timedelta(days=1)).date().isoformat(),
        created_at=now_iso(),
        updated_at=now_iso(),
    ),
    2: Task(
        id=2,
        title="Chuẩn bị slide hội thảo",
        description="Hoàn thiện slide 15 phút",
        assignee="Lan",
        status="in_progress",
        priority="medium",
        due_date=(datetime.now() - timedelta(days=1)).date().isoformat(),
        created_at=now_iso(),
        updated_at=now_iso(),
    ),
    3: Task(
        id=3,
        title="Chốt lịch họp BTC",
        description="Xác nhận lịch với các bên liên quan",
        assignee="Minh",
        status="done",
        priority="low",
        due_date=(datetime.now() + timedelta(days=5)).date().isoformat(),
        created_at=now_iso(),
        updated_at=now_iso(),
    ),
}

task_history_db: Dict[int, List[TaskHistoryItem]] = {
    1: [
        TaskHistoryItem(
            id=1,
            task_id=1,
            action="created",
            detail="Tạo task",
            created_at=now_iso(),
        )
    ],
    2: [
        TaskHistoryItem(
            id=2,
            task_id=2,
            action="created",
            detail="Tạo task",
            created_at=now_iso(),
        ),
        TaskHistoryItem(
            id=3,
            task_id=2,
            action="status_changed",
            detail="Chuyển trạng thái sang in_progress",
            created_at=now_iso(),
        ),
    ],
    3: [
        TaskHistoryItem(
            id=4,
            task_id=3,
            action="created",
            detail="Tạo task",
            created_at=now_iso(),
        ),
        TaskHistoryItem(
            id=5,
            task_id=3,
            action="status_changed",
            detail="Chuyển trạng thái sang done",
            created_at=now_iso(),
        ),
    ],
}

next_task_id = 4
next_history_id = 6


def add_history(task_id: int, action: str, detail: str):
    global next_history_id
    item = TaskHistoryItem(
        id=next_history_id,
        task_id=task_id,
        action=action,
        detail=detail,
        created_at=now_iso(),
    )
    next_history_id += 1
    task_history_db.setdefault(task_id, []).insert(0, item)
    return item


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead_connections: List[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                dead_connections.append(connection)

        for conn in dead_connections:
            self.disconnect(conn)


manager = ConnectionManager()


def serialize_task(task: Task):
    return task.model_dump()


def task_ai_suggestion(task: Task) -> dict:
    suggestions = []

    if task.status != "done" and task.due_date:
        try:
            due = datetime.fromisoformat(task.due_date)
            if due.date() < datetime.now().date():
                suggestions.append("Task đang overdue. Ưu tiên xử lý ngay hoặc dời hạn hợp lý.")
        except Exception:
            pass

    if not task.assignee:
        suggestions.append("Task chưa có người phụ trách. Nên gán assignee rõ ràng.")

    if len(task.description.strip()) < 15:
        suggestions.append("Mô tả task còn ngắn. Nên bổ sung đầu việc, đầu ra, thời hạn.")

    if task.priority == "high" and task.status == "todo":
        suggestions.append("Task ưu tiên cao nhưng chưa bắt đầu. Nên chuyển sang in_progress nếu đã phân công.")

    if task.status == "in_progress":
        suggestions.append("Nên cập nhật tiến độ định kỳ vào history để theo dõi dễ hơn.")

    if task.status == "done":
        suggestions.append("Task đã hoàn thành. Kiểm tra đầu ra cuối cùng trước khi đóng việc.")

    if not suggestions:
        suggestions.append("Task đang ở trạng thái tương đối ổn. Chỉ cần theo dõi deadline và cập nhật history.")

    return {
        "summary": f"Gợi ý AI cho task '{task.title}'",
        "suggestions": suggestions,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@app.get("/tasks")
async def get_tasks():
    return [serialize_task(task) for task in tasks_db.values()]


@app.get("/tasks/{task_id}")
async def get_task_detail(task_id: int):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return serialize_task(task)


@app.get("/tasks/{task_id}/history")
async def get_task_history(task_id: int):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return [item.model_dump() for item in task_history_db.get(task_id, [])]


@app.post("/tasks")
async def create_task(payload: TaskCreate):
    global next_task_id

    created = Task(
        id=next_task_id,
        title=payload.title,
        description=payload.description or "",
        assignee=payload.assignee or "",
        status=payload.status or "todo",
        priority=payload.priority or "medium",
        due_date=payload.due_date,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    tasks_db[next_task_id] = created
    add_history(created.id, "created", "Tạo task mới")
    next_task_id += 1

    await manager.broadcast({
        "type": "task_created",
        "title": "Task mới",
        "message": f"Đã tạo task: {created.title}",
        "task_id": created.id,
    })

    return created.model_dump()


@app.put("/tasks/{task_id}")
async def update_task(task_id: int, payload: TaskUpdate):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    changes = []

    if payload.title is not None and payload.title != task.title:
        changes.append(f"title: '{task.title}' -> '{payload.title}'")
        task.title = payload.title

    if payload.description is not None and payload.description != task.description:
        changes.append("description updated")
        task.description = payload.description

    if payload.assignee is not None and payload.assignee != task.assignee:
        changes.append(f"assignee: '{task.assignee}' -> '{payload.assignee}'")
        task.assignee = payload.assignee

    if payload.status is not None and payload.status != task.status:
        changes.append(f"status: '{task.status}' -> '{payload.status}'")
        task.status = payload.status

    if payload.priority is not None and payload.priority != task.priority:
        changes.append(f"priority: '{task.priority}' -> '{payload.priority}'")
        task.priority = payload.priority

    if payload.due_date is not None and payload.due_date != task.due_date:
        changes.append(f"due_date: '{task.due_date}' -> '{payload.due_date}'")
        task.due_date = payload.due_date

    task.updated_at = now_iso()
    tasks_db[task_id] = task

    if changes:
        add_history(task_id, "updated", "; ".join(changes))
    else:
        add_history(task_id, "updated", "Cập nhật task")

    await manager.broadcast({
        "type": "task_updated",
        "title": "Task đã cập nhật",
        "message": f"Task '{task.title}' vừa được chỉnh sửa",
        "task_id": task.id,
    })

    if task.status == "done":
        add_history(task_id, "completed", "Đánh dấu hoàn thành")
        await manager.broadcast({
            "type": "task_completed",
            "title": "Hoàn thành công việc",
            "message": f"Task '{task.title}' đã hoàn thành",
            "task_id": task.id,
        })

    return task.model_dump()


@app.patch("/tasks/{task_id}/status")
async def update_task_status(task_id: int, payload: TaskStatusUpdate):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.status
    task.status = payload.status
    task.updated_at = now_iso()
    tasks_db[task_id] = task

    add_history(task_id, "status_changed", f"Chuyển trạng thái từ '{old_status}' sang '{task.status}'")

    await manager.broadcast({
        "type": "task_updated",
        "title": "Cập nhật trạng thái",
        "message": f"Task '{task.title}' chuyển từ '{old_status}' sang '{task.status}'",
        "task_id": task.id,
    })

    if task.status == "done":
        add_history(task_id, "completed", "Đánh dấu hoàn thành")
        await manager.broadcast({
            "type": "task_completed",
            "title": "Hoàn thành công việc",
            "message": f"Task '{task.title}' đã hoàn thành",
            "task_id": task.id,
        })

    return task.model_dump()


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    deleted = tasks_db.pop(task_id)
    task_history_db.pop(task_id, None)

    await manager.broadcast({
        "type": "task_deleted",
        "title": "Đã xóa task",
        "message": f"Task '{deleted.title}' đã bị xóa",
        "task_id": task_id,
    })

    return {"success": True}


@app.post("/ai/suggest")
async def ai_suggest(payload: AIRequest):
    task = tasks_db.get(payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_ai_suggestion(task)
