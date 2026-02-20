from __future__ import annotations

import uuid
from typing import Any, Dict, Tuple, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

SID_COOKIE = "sid"
SID_HEADER = "x-sid"          # 프론트가 헤더로 보낼 수도 있어서
CLIENT_ID_HEADER = "x-client-id"  # progress용(없으면 sid로 대체)


def _new_sid() -> str:
    return uuid.uuid4().hex


def _get_or_create_sid(request: Request) -> Tuple[str, bool]:
    """
    sid 우선순위:
    1) Cookie["sid"]
    2) Header["x-sid"]
    3) 새로 생성
    """
    sid = request.cookies.get(SID_COOKIE)
    if sid and isinstance(sid, str) and sid.strip():
        return sid.strip(), False

    sid_h = request.headers.get(SID_HEADER)
    if sid_h and isinstance(sid_h, str) and sid_h.strip():
        return sid_h.strip(), False

    return _new_sid(), True


def _get_client_id(request: Request) -> str:
    """
    progress SSE/폴링에서 client 식별키로 사용.
    - 프론트가 x-client-id를 주면 그걸 쓰고
    - 없으면 sid로 대체
    """
    cid = request.headers.get(CLIENT_ID_HEADER)
    if cid and isinstance(cid, str) and cid.strip():
        return cid.strip()

    sid, _ = _get_or_create_sid(request)
    return sid


def _json_with_sid(payload: Dict[str, Any], sid: str, sid_is_new: bool) -> JSONResponse:
    """
    응답 JSON에 sid를 포함시키고(프론트가 참고용),
    sid가 새로 발급된 경우 쿠키로도 심어줌.
    """
    if not isinstance(payload, dict):
        payload = {"data": payload}

    payload.setdefault("sid", sid)

    resp = JSONResponse(payload)
    if sid_is_new:
        # 개발환경 기본: samesite=lax, httponly=False(프론트 디버깅 편의)
        # 운영 가면 httponly/secure 조정
        resp.set_cookie(
            key=SID_COOKIE,
            value=sid,
            httponly=False,
            samesite="lax",
            secure=False,
            max_age=60 * 60 * 24 * 30,  # 30일
        )
    return resp