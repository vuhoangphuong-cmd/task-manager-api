from pydantic import BaseModel
import os

class Settings(BaseModel):
    app_name: str = "Task Manager API"
    db_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://taskuser:StrongPassword123!@localhost:5432/taskdb"
    )

settings = Settings()
