import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

# Secret settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # 2 hours
TOKEN_COOKIE_NAME = "access_token"

# Use argon2 to avoid bcrypt 72 byte limit issues with passlib
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def is_password_hash(value: str) -> bool:
    if not value:
        return False
    try:
        return pwd_context.identify(value) is not None
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def _cookie_secure() -> bool:
    raw = os.getenv("COOKIE_SECURE", "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return False


def _cookie_samesite() -> str:
    raw = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
    if raw in ("lax", "strict", "none"):
        return raw
    return "lax"


def set_access_cookie(response, token: str) -> None:
    samesite = _cookie_samesite()
    secure = _cookie_secure()
    if samesite == "none":
        secure = True
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=samesite,
        secure=secure,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def clear_access_cookie(response) -> None:
    response.delete_cookie(TOKEN_COOKIE_NAME, path="/")
