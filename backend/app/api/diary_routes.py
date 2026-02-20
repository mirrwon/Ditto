import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/diary")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIARY_DIR = os.path.join(BASE_DIR, "diary_record")
os.makedirs(DIARY_DIR, exist_ok=True)
DIARY_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(DIARY_UPLOAD_DIR, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_path(diary_id: str) -> str:
    return os.path.join(DIARY_DIR, f"{diary_id}.json")


def _load_record(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Diary not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_record(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_upload(file: UploadFile, diary_id: str) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    filename = f"{diary_id}{ext}"
    dest = os.path.join(DIARY_UPLOAD_DIR, filename)
    with open(dest, "wb") as f:
        f.write(file.file.read())
    return filename


@router.get("")
def list_diary(current_user: dict = Depends(get_current_user)) -> JSONResponse:
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    items: List[Dict[str, Any]] = []
    for name in os.listdir(DIARY_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(DIARY_DIR, name)
        try:
            record = _load_record(path)
            if record.get("username") != username:
                continue
            items.append(record)
        except Exception:
            continue
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return JSONResponse({"items": items})


@router.get("/{diary_id}")
def get_diary(
    diary_id: str,
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    record = _load_record(_record_path(diary_id))
    if record.get("username") != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    return JSONResponse(record)


@router.post("")
def create_diary(
    title: str = Form(...),
    content: str = Form(...),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    diary_id = str(uuid4())
    now = _now_iso()
    record: Dict[str, Any] = {
        "id": diary_id,
        "title": title,
        "content": content,
        "username": username,
        "created_at": now,
        "updated_at": now,
    }
    if image:
        record["image_filename"] = _save_upload(image, diary_id)
    _save_record(_record_path(diary_id), record)
    return JSONResponse(record, status_code=201)


@router.put("/{diary_id}")
def update_diary(
    diary_id: str,
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    path = _record_path(diary_id)
    record = _load_record(path)
    if record.get("username") != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    if title is not None:
        record["title"] = title
    if content is not None:
        record["content"] = content
    if image:
        record["image_filename"] = _save_upload(image, diary_id)
    record["updated_at"] = _now_iso()
    _save_record(path, record)
    return JSONResponse(record)


@router.delete("/{diary_id}")
def delete_diary(
    diary_id: str,
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    path = _record_path(diary_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Diary not found")
    record = _load_record(path)
    if record.get("username") != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    os.remove(path)
    return JSONResponse({"ok": True, "id": diary_id})
