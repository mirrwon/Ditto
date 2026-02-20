import base64
import json
import os
import secrets
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional


from fastapi import APIRouter, Form, HTTPException, UploadFile, File, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
import requests
from app.api.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    is_password_hash,
    set_access_cookie,
    clear_access_cookie,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(BASE_DIR, "users")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
RESULT_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(USER_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

UPLOAD_MOUNT = "/auth-uploads"
ALLOWED_RESULT_EXTS = {".png", ".jpg", ".jpeg", ".jfif", ".gif", ".webp"}
OAUTH_STATE_TTL_SEC = 600
_oauth_state_cache = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_username(name: str) -> str:
    return name.replace(os.sep, "_").replace(os.altsep or "", "_")


def _user_path(username: str) -> str:
    safe = _safe_username(username)
    return os.path.join(USER_DIR, f"{safe}.json")


def _save_profile_image(file: UploadFile, username: str) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    safe = _safe_username(username)
    filename = f"profile_{safe}{ext}"
    dest = os.path.join(UPLOAD_DIR, filename)
    with open(dest, "wb") as f:
        f.write(file.file.read())
    return filename


def _build_profile_image_url(request: Request, filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}{UPLOAD_MOUNT}/{filename}"


def _load_user(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="User not found")
    with open(path, "r", encoding="utf-8") as f:
        record = json.load(f)
    if _normalize_user_record(record):
        _save_user(path, record)
    return record


def _save_user(path: str, data: Dict[str, Any]) -> None:
    _normalize_user_record(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_user_record(data: Dict[str, Any]) -> bool:
    changed = False
    if "user_name" in data:
        if "username" in data:
            data.pop("username", None)
            changed = True
    elif "username" in data:
        data["user_name"] = data.pop("username")
        changed = True
    return changed


def _verify_or_migrate_password(record: Dict[str, Any], password: str) -> tuple[bool, bool]:
    stored = record.get("password") or ""
    if not stored:
        return False, False

    if is_password_hash(stored):
        try:
            return verify_password(password, stored), False
        except Exception:
            return False, False

    if stored == password:
        record["password"] = get_password_hash(password)
        return True, True

    return False, False


def _cleanup_oauth_state() -> None:
    now = time.time()
    expired = [key for key, ts in _oauth_state_cache.items() if now - ts > OAUTH_STATE_TTL_SEC]
    for key in expired:
        _oauth_state_cache.pop(key, None)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=500, detail=f"Missing {name}")
    return value


def _google_oauth_config() -> Dict[str, str]:
    return {
        "client_id": _require_env("GOOGLE_CLIENT_ID"),
        "client_secret": _require_env("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": _require_env("GOOGLE_REDIRECT_URI"),
    }


def _encode_oauth_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _is_result_image(name: str, path: str) -> bool:
    if not os.path.isfile(path):
        return False
    _, ext = os.path.splitext(name)
    return ext.lower() in ALLOWED_RESULT_EXTS


def _next_user_num() -> int:
    # Incremental numeric id based on existing users.
    max_id = 0
    for filename in os.listdir(USER_DIR):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(USER_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            value = str(data.get("user_num", "")).strip()
            if value.isdigit():
                max_id = max(max_id, int(value))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return max_id + 1


def _oauth_user_record(
    username: str,
    email: Optional[str],
    name: Optional[str],
    sub: str,
) -> Dict[str, Any]:
    return {
        "user_num": str(_next_user_num()),
        "user_name": username,
        "password": "google-oauth",
        "name": name or username,
        "birthDate": "",
        "phone": "",
        "email": email or "",
        "gender": "",
        "zipcode": "",
        "address1": "",
        "address2": "",
        "provider": "google",
        "oauth_sub": sub,
        "created_at": _now_iso(),
    }


def _needs_profile(record: Dict[str, Any]) -> bool:
    required = ["gender", "birthDate", "phone", "zipcode", "address1"]
    for key in required:
        value = str(record.get(key, "")).strip()
        if not value:
            return True
    return False


@router.get("/google")
def google_login() -> RedirectResponse:
    config = _google_oauth_config()
    _cleanup_oauth_state()
    state = secrets.token_urlsafe(24)
    _oauth_state_cache[state] = time.time()
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(auth_url)


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    _cleanup_oauth_state()
    if state and state not in _oauth_state_cache:
        raise HTTPException(status_code=400, detail="Invalid state")
    if state:
        _oauth_state_cache.pop(state, None)

    config = _google_oauth_config()
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": config["redirect_uri"],
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not token_resp.ok:
        raise HTTPException(status_code=400, detail="Token exchange failed")
    token_data = token_resp.json()
    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Missing id_token")

    info_resp = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": id_token},
        timeout=10,
    )
    if not info_resp.ok:
        raise HTTPException(status_code=400, detail="Token verification failed")
    info = info_resp.json()
    if info.get("aud") != config["client_id"]:
        raise HTTPException(status_code=400, detail="Invalid audience")

    email = info.get("email")
    sub = info.get("sub") or ""
    name = info.get("name")
    picture = info.get("picture")

    username = email or f"google_{sub}"
    path = _user_path(username)
    if os.path.exists(path):
        record = _load_user(path)
    else:
        record = _oauth_user_record(username, email, name, sub)
        _save_user(path, record)

    response = {k: v for k, v in record.items() if k != "password"}
    profile_url = _build_profile_image_url(request, record.get("profile_image_filename"))
    response["profileImageUrl"] = profile_url or picture
    response["needsProfile"] = _needs_profile(record)

    frontend_redirect = os.getenv("FRONTEND_OAUTH_REDIRECT", "http://localhost:3000/login")
    payload = _encode_oauth_payload(response)
    redirect_url = f"{frontend_redirect}?oauth=google&payload={urllib.parse.quote(payload)}"
    access_token = create_access_token(data={"sub": username})
    resp = RedirectResponse(redirect_url)
    set_access_cookie(resp, access_token)
    return resp


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    birthDate: str = Form(...),
    phone: str = Form(...),
    email: str = Form(...),
    profileImage: Optional[UploadFile] = File(None),
    gender: Optional[str] = Form(None),
    zipcode: Optional[str] = Form(None),
    address1: Optional[str] = Form(None),
    address2: Optional[str] = Form(None),
) -> JSONResponse:
    path = _user_path(username)
    if os.path.exists(path):
        raise HTTPException(status_code=409, detail="Username already exists")

    record: Dict[str, Any] = {
        "user_num": str(_next_user_num()),
        "user_name": username,
        "password": get_password_hash(password),
        "name": name,
        "birthDate": birthDate,
        "phone": phone,
        "email": email,
        "gender": gender,
        "zipcode": zipcode,
        "address1": address1,
        "address2": address2,
        "created_at": _now_iso(),
    }

    if profileImage:
        record["profile_image_filename"] = _save_profile_image(profileImage, username)

    _save_user(path, record)

    response = {k: v for k, v in record.items() if k != "password"}
    response["profileImageUrl"] = _build_profile_image_url(
        request, record.get("profile_image_filename")
    )
    access_token = create_access_token(data={"sub": username})
    resp = JSONResponse(response, status_code=201)
    set_access_cookie(resp, access_token)
    return resp


@router.post("/login")
def login(payload: Dict[str, Any], request: Request) -> JSONResponse:
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    record = _load_user(_user_path(username))
    ok, migrated = _verify_or_migrate_password(record, password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if migrated:
        _save_user(_user_path(username), record)

    response = {k: v for k, v in record.items() if k != "password"}
    response["profileImageUrl"] = _build_profile_image_url(
        request, record.get("profile_image_filename")
    )
    access_token = create_access_token(data={"sub": username})
    resp = JSONResponse(response)
    set_access_cookie(resp, access_token)
    return resp


@router.put("/profile")
def update_profile(
    request: Request,
    current_user: dict = Depends(get_current_user),
    password: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    birthDate: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    profileImage: Optional[UploadFile] = File(None),
    gender: Optional[str] = Form(None),
    zipcode: Optional[str] = Form(None),
    address1: Optional[str] = Form(None),
    address2: Optional[str] = Form(None),
) -> JSONResponse:
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    path = _user_path(username)
    record = _load_user(path)

    updates = {
        "name": name,
        "birthDate": birthDate,
        "phone": phone,
        "email": email,
        "gender": gender,
        "zipcode": zipcode,
        "address1": address1,
        "address2": address2,
    }
    for key, value in updates.items():
        if value is not None:
            record[key] = value

    is_oauth_user = record.get("provider") == "google" or bool(record.get("oauth_sub"))
    if password and is_oauth_user:
        raise HTTPException(status_code=400, detail="OAuth users cannot change password")

    if password:
        record["password"] = get_password_hash(password)

    if profileImage:
        record["profile_image_filename"] = _save_profile_image(profileImage, username)

    _save_user(path, record)

    response = {k: v for k, v in record.items() if k != "password"}
    response["profileImageUrl"] = _build_profile_image_url(
        request, record.get("profile_image_filename")
    )
    return JSONResponse(response)


@router.post("/logout")
def logout() -> JSONResponse:
    resp = JSONResponse({"ok": True})
    clear_access_cookie(resp)
    return resp


@router.get("/results")
def list_results() -> JSONResponse:
    items = []
    for name in os.listdir(RESULT_DIR):
        path = os.path.join(RESULT_DIR, name)
        if not _is_result_image(name, path):
            continue
        items.append(
            {
                "name": name,
                "url": f"/results/{name}",
                "mtime": os.path.getmtime(path),
            }
        )
    items.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return JSONResponse({"items": items})
