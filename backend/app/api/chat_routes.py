from __future__ import annotations

from fastapi import APIRouter, Request, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from typing import Optional, List
from app.api.deps import get_current_user

from .chat_progress import stream_route
from .chat_handlers import (
    chat_get,
    chat_post,
    chat_image,
    chat_pick_spot,
    get_filters,
    PickSpotBody,
    get_results,
    get_scenes,
    get_scenes_all,
    handle_chat_analyze,
    AnalyzeBody,
    chat_render,
    handle_chat_recommend, RecommendBody
)

from .chat_survey import survey_router

router = APIRouter()

# survey API 호출
router.include_router(survey_router)

# -------------------------
# v3 Contract: /api/chat/filters
# -------------------------
@router.get("/api/chat/filters")
def route_filters():
    return get_filters()

# ✅ room group options만 반환
@router.get("/api/chat/scenes")
def route_scenes():
    return get_scenes()

# ✅ 전체 scene 리스트(라벨 포함) 반환
@router.get("/api/chat/scenes/all")
def route_scenes_all():
    return get_scenes_all()

# -------------------------
# v3 Contract: /api/chat/stream (SSE heartbeat) - 절대 제거 금지
# -------------------------
@router.get("/api/chat/stream")
def route_stream(request: Request):
    return stream_route(request)

@router.get("/api/chat")
async def route_chat_get(request: Request, current_user: dict = Depends(get_current_user)):
    return await chat_get(request)

@router.post("/api/chat")
async def route_chat_post(request: Request, current_user: dict = Depends(get_current_user)):
    return await chat_post(request)

@router.post("/api/chat/image")
async def route_chat_image(
    request: Request,
    current_user: dict = Depends(get_current_user),
    files: Optional[List[UploadFile]] = File(None),
    image: Optional[UploadFile] = File(None),
    meta: Optional[str] = Form(None),
    scene_id: Optional[str] = Form(None),
    room_type: Optional[str] = Form(None),
):
    return await chat_image(
        request,
        files=files,
        image=image,
        meta=meta,
        scene_id=scene_id,
        room_type=room_type,
    )

@router.post("/api/chat/spot")
async def route_chat_spot(
    request: Request,
    body: PickSpotBody,
    current_user: dict = Depends(get_current_user),
):
    return await chat_pick_spot(request, body)

@router.get("/api/chat/results")
def route_results(current_user: dict = Depends(get_current_user)):
    return get_results()

@router.post("/api/chat/analyze")
async def chat_analyze(
    request: Request,
    body: AnalyzeBody,
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    return await handle_chat_analyze(request, body)

# -------------------------
# Page-specific aliases (NEW)
# 3페이지: 9개 추천
# 4페이지: 선택 식물 spot 이미지 생성
# -------------------------

@router.post("/api/chat/recommend")
async def chat_recommend(request: Request, body: RecommendBody) -> JSONResponse:
    return await handle_chat_recommend(request, body)

@router.post("/api/chat/render")
async def route_chat_render(request: Request, body: PickSpotBody) -> JSONResponse:
    # ✅ 기존 spot 로직 재사용
    return await chat_pick_spot(request, body)

@router.get("/api/chat/render")
def chat_render_get():
    return JSONResponse(
        {"ok": False, "hint": "Use POST /api/chat/render with JSON {spot_index, regen}"},
        status_code=200,
    )