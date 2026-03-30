import json
from datetime import datetime
from pathlib import Path

from app.db import SessionLocal, Base, engine
from app.models import Task, TaskHistory

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "tasks_data.json"


def parse_dt(value: str | None):
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.utcnow()


def main():
    Base.metadata.create_all(bind=engine)

    if not DATA_FILE.exists():
        print("Không thấy tasks_data.json, bỏ qua import.")
        return

    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    tasks = raw.get("tasks", [])
    history = raw.get("history", [])

    db = SessionLocal()
    try:
        existing_tasks = db.query(Task).count()
        existing_history = db.query(TaskHistory).count()
        if existing_tasks > 0 or existing_history > 0:
            print("Database đã có dữ liệu, dừng để tránh import trùng.")
            return

        for item in tasks:
            db.add(
                Task(
                    id=item["id"],
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    assignee=item.get("assignee", ""),
                    priority=item.get("priority", "medium"),
                    due_date=item.get("due_date"),
                    status=item.get("status", "todo"),
                    created_at=parse_dt(item.get("created_at")),
                    updated_at=parse_dt(item.get("updated_at")),
                )
            )

        db.commit()

        for item in history:
            db.add(
                TaskHistory(
                    id=item["id"],
                    task_id=item["task_id"],
                    action=item.get("action", ""),
                    detail=item.get("detail", ""),
                    created_at=parse_dt(item.get("created_at")),
                )
            )

        db.commit()
        print(f"Đã import {len(tasks)} tasks và {len(history)} history items.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
