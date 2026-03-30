from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.tasks import router as tasks_router
from app.api.users import router as users_router
from app.api.reports import router as reports_router
from app.api.dashboard import router as dashboard_router
from app.api.assistant import router as assistant_router
from app.ws_manager import manager

app = FastAPI(title="Task Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.websocket("/ws/tasks")
async def websocket_tasks(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(reports_router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(assistant_router, prefix="/api/v1/assistant", tags=["assistant"])
