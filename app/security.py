from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.settings import get_settings

settings = get_settings()
password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire_minutes = expires_minutes or settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": subject,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
