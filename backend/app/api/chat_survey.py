from __future__ import annotations

import os
import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, Depends

from app.config import BASE_DIR, UPLOAD_DIR, RESULT_DIR
from app.cv.pipeline import run_pipeline
from app.llm.image_edit import composite_plant_on_original

from .chat_session import _get_or_create_sid
from .chat_storage import get_user_ctx, set_user_ctx
from .chat_utils import abs_url, extract_best_point
from app.api.deps import get_current_user

survey_router = APIRouter()

# in-memory uploads tracker (세션 기준)
SURVEY_UPLOADS: Dict[str, List[Dict[str, str]]] = {}

SURVEY_DIR = os.path.join(BASE_DIR, "surveys")
os.makedirs(SURVEY_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)


def _safe_key(name: str) -> str:
    safe = name.replace(os.sep, "_")
    if os.altsep:
        safe = safe.replace(os.altsep, "_")
    return safe


def _survey_path(key: str) -> str:
    safe = _safe_key(key or "anonymous")
    return os.path.join(SURVEY_DIR, f"{safe}.jsonl")


def _next_survey_id(key: str) -> int:
    path = _survey_path(key)
    if not os.path.exists(path):
        return 1
    last_id = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                try:
                    last_id = max(last_id, int(obj.get("id", 0)))
                except Exception:
                    continue
    except Exception:
        return last_id + 1 if last_id else 1
    return last_id + 1 if last_id else 1


def _append_survey(key: str, record: Dict[str, Any]) -> None:
    path = _survey_path(key)
    record = {"id": _next_survey_id(key), **record}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# -------------------------
# v3 Contract: GET /api/chat/survey
# -------------------------
@survey_router.get("/api/chat/survey")
def get_survey(current_user: dict = Depends(get_current_user)):
    return {
        "key": "style_survey",
        "label": "선호 스타일 선택",
        "ui": "checkbox",
        "description": "",
        "groups": [
            {
                "key": "caution",
                "multiple": True,
                "label": "주의 사항을 선택해 주세요",
                "options": [
                    {"value": "", "label": "없음"},
                    {"value": "baby", "label": "아이"},
                    {"value": "dog", "label": "강아지"},
                    {"value": "cat", "label": "고양이"},
                    {"value": "allergy", "label": "알러지"},
                ],
            },
            {
                "key": "size",
                "multiple": True,
                "label": "원하는 식물 크기는 무엇인가요?",
                "options": [
                    {"value": "", "label": "없음"},
                    {"value": "small", "label": "탁상용"},
                    {"value": "large", "label": "바닥용"},
                ],
            },
            {
                "key": "style",
                "multiple": True,
                "label": "방 분위기를 선택해주세요.",
                "options": [
                    {"value": "", "label": "없음", "image": "/assets/survey/none.png"},
                    {"value": "natural", "label": "내추럴", "image": "/assets/survey/natural.jpg"},
                    {"value": "minimal", "label": "미니멀", "image": "/assets/survey/minimal.jpg"},
                    {"value": "trendy", "label": "트렌디", "image": "/assets/survey/trendy.jpg"},
                ],
            },
            {
                "key": "Plant_style",
                "multiple": True,
                "label": "당신이 원하는 식물 스타일은 무엇인가요?",
                "options": [
                    {"value": "", "label": "없음", "image": "/assets/survey/none.png"},
                    {"value": "flowery", "label": "화려한 꽃", "image": "/assets/survey/flowery.jpg"},
                    {"value": "leafy", "label": "푸른 잎", "image": "/assets/survey/leafy.png"},
                    {"value": "fruity", "label": "싱그러운 과일", "image": "/assets/survey/fruity.jpg"},
                ],
            },
        ],
    }


# -------------------------
# v3 Contract: POST /api/chat/survey
# -------------------------
@survey_router.post("/api/chat/survey")
async def submit_survey(request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()

    sid, _ = _get_or_create_sid(request)
    key = sid
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    # "설문 이미지를 먼저 올려야 한다" 룰 유지

    # if not SURVEY_UPLOADS.get(key):
    #     raise HTTPException(status_code=400, detail="survey_image_required")

    answers = body.get("answers") if isinstance(body, dict) else None
    if isinstance(answers, dict):
        # 세션 컨텍스트에 survey 저장
        ctx = get_user_ctx(key)
        if not isinstance(ctx, dict):
            ctx = {}
        ctx["survey"] = answers
        set_user_ctx(key, ctx, ttl_sec=60 * 60 * 6)

        # JSONL에도 저장(구형 로직 유지, 단 username 대신 sid 기준)
        _append_survey(sid, {"answers": answers})

    return {"ok": True, "received": body}


# -------------------------
# v3 Contract: POST /api/chat/survey/image (upload)
# -------------------------
@survey_router.post("/api/chat/survey/image")
async def survey_image_upload(
    request: Request,
    current_user: dict = Depends(get_current_user),
    files: Optional[List[UploadFile]] = File(None),
    image: Optional[UploadFile] = File(None),
    survey_key: Optional[str] = Form(None),
):
    username = current_user.get("user_name")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    sid, _ = _get_or_create_sid(request)
    key = sid

    uploads: List[UploadFile] = []
    if files and len(files) > 0:
        uploads = files
    elif image is not None:
        uploads = [image]

    if not uploads:
        return {"ok": False, "reason": "no_files", "message": "No files uploaded."}

    saved_items: List[Dict[str, str]] = []
    first_saved_path: Optional[str] = None

    for idx, upload in enumerate(uploads):
        filename = upload.filename or f"survey_{idx}.jpg"
        _, ext = os.path.splitext(filename)
        ext = ext if ext else ".jpg"
        safe_name = f"survey_{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(UPLOAD_DIR, safe_name)

        content = await upload.read()
        with open(save_path, "wb") as f:
            f.write(content)

        if first_saved_path is None:
            first_saved_path = save_path

        saved_items.append({"name": safe_name, "url": abs_url(request, f"/uploads/{safe_name}")})

    # 구형 로직: survey 업로드 첫 이미지에 대해 CV + marker/composite 생성
    if first_saved_path:
        try:
            run_pipeline(first_saved_path, debug_viz=True)
        except TypeError:
            run_pipeline(first_saved_path)

        try:
            latest_json = os.path.join(RESULT_DIR, "result_latest.json")
            data: Dict[str, Any] = {}
            if os.path.exists(latest_json):
                with open(latest_json, "r", encoding="utf-8") as f:
                    data = json.load(f)

            best_point = extract_best_point(data)
            marker_path = os.path.join(RESULT_DIR, "result_latest_marker.png")
            composite_path = os.path.join(RESULT_DIR, "result_latest_composite.png")
            plant_asset = os.path.join(BASE_DIR, "assets", "plants", "default.png")

            composite_plant_on_original(
                original_image_path=first_saved_path,
                best_point_obj=best_point,
                out_path=marker_path,
                plant_png_path=None,
                add_green_dot=True,
                plant_width_ratio=0.22,
                anchor="bottom_center",
            )

            composite_plant_on_original(
                original_image_path=first_saved_path,
                best_point_obj=best_point,
                out_path=composite_path,
                plant_png_path=plant_asset if os.path.exists(plant_asset) else None,
                plant_width_ratio=0.22,
                anchor="bottom_center",
                add_green_dot=True,
            )
        except Exception as e:
            print("[WARN] survey marker/composite generation failed:", e)

    SURVEY_UPLOADS.setdefault(key, []).extend(saved_items)

    return {"ok": True, "survey_key": survey_key, "items": saved_items}
