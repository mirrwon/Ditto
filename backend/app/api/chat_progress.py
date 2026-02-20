from __future__ import annotations

import json
import time
from queue import Queue
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

# client_id -> Queue
CLIENT_QUEUES: Dict[str, Queue] = {}

PROGRESS_MSG: Dict[str, str] = {
    "upload": "이미지를 저장했어요. 분석을 시작할게요.",
    "cv_start": "이미지에서 바닥/벽/창문을 분석 중이에요.",
    "cv_floor": "바닥 영역을 찾고 있어요.",
    "cv_window": "창문 후보를 찾고 있어요.",
    "cv_light": "채광 방향/빛 영역을 계산 중이에요.",
    "cv_done": "CV 분석이 끝났어요. 추천을 준비할게요.",
    "scene_required": "사진 구도가 애매해요. 장면을 선택해 주세요.",
    "solar": "태양광(일조) 조건을 조회 중이에요.",
    "result_load": "분석 결과를 불러오는 중이에요.",
    "recommend": "추천 식물을 고르는 중이에요...",
    "compose": "추천 위치를 이미지에 표시 중이에요.",
    "respond": "결과를 정리해서 보내는 중이에요.",
    "error": "오류가 발생했어요. 로그를 확인해 주세요.",
}


def _get_queue(cid: str) -> Queue:
    q = CLIENT_QUEUES.get(cid)
    if q is None:
        q = Queue()
        CLIENT_QUEUES[cid] = q
    return q


def push_progress(cid: str, step: str, text: str) -> None:
    """
    큐에 progress payload를 넣는다.
    프론트는 SSE stream에서 이 payload를 받는다.
    """
    q = _get_queue(cid)
    payload: Dict[str, Any] = {
        "messages": [
            {
                "type": "progress",
                "role": "bot",
                "text": text,
                "payload": {"progress": {"step": step}},
                "timestamp": int(time.time() * 1000),
            }
        ]
    }
    q.put(payload)


def progress(cid: str, step: str, msg: Optional[str] = None) -> None:
    """
    chat_handlers 등에서 쓰는 API.
    step만 주면 기본 메시지(PROGRESS_MSG)를 사용.
    """
    push_progress(cid, step, msg or PROGRESS_MSG.get(step, step))


def chat_stream(request: Request) -> StreamingResponse:
    """
    기존 /api/chat/stream 라우트에서 그대로 사용.
    """
    from .chat_session import _get_client_id  # 순환 import 방지

    cid = _get_client_id(request)
    q = _get_queue(cid)

    def gen():
        # 최초 heartbeat
        yield "event: heartbeat\ndata: {}\n\n"
        while True:
            try:
                item = q.get(timeout=15)
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            except Exception:
                yield "event: heartbeat\ndata: {}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    resp = StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
    resp.set_cookie("cid", cid, httponly=False, samesite="lax")
    return resp


def stream_route(request: Request):
    return chat_stream(request)