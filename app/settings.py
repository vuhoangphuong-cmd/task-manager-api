from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Task Manager API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/task_manager"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://172.25.77.171:5173"
    secret_key: str = "super-secret-key-change-this-later-123456789"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings():
    return Settings()
