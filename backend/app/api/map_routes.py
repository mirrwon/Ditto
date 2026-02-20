import json
import os
from typing import Any, Dict

import requests
from fastapi import APIRouter, HTTPException, Depends
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/map")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DIR = os.path.join(BASE_DIR, "users")

KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"


def _safe_username(name: str) -> str:
    return name.replace(os.sep, "_").replace(os.altsep or "", "_")


def _user_path(username: str) -> str:
    safe = _safe_username(username)
    return os.path.join(USER_DIR, f"{safe}.json")


def _load_user(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="User not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_kakao_key() -> str:
    candidates = [
        os.getenv("KAKAO_REST_API_KEY", ""),
        os.getenv("REST_API_KEY", ""),
        os.getenv("KAKAO_API_KEY", ""),
    ]
    for value in candidates:
        key = value.strip().strip('"').strip("'")
        if key:
            return key
    raise HTTPException(status_code=500, detail="Missing Kakao REST API key")


def _kakao_headers() -> Dict[str, str]:
    key = _get_kakao_key()
    return {"Authorization": f"KakaoAK {key}"}


def _build_address(record: Dict[str, Any]) -> str:
    address1 = str(record.get("address1", "") or "").strip()
    address2 = str(record.get("address2", "") or "").strip()
    # Use address1 for geocoding; address2 is typically a detail unit number.
    if address1:
        return address1
    return address2


def _request_kakao(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = requests.get(
            url, headers=_kakao_headers(), params=params, timeout=10
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Kakao request failed: {exc}") from exc

    if not response.ok:
        detail = response.text or "Kakao API error"
        # Do not leak upstream auth status as our session/auth failure.
        # Frontend treats 401 as local session expiry.
        if response.status_code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail=f"Kakao API auth failed ({response.status_code})",
            )
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()


def _clamp_int(value: int, min_value: int, max_value: int, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(min_value, min(parsed, max_value))


def _find_nearest_parking(x: str, y: str, radius: int) -> Dict[str, Any] | None:
    payload = _request_kakao(
        KAKAO_CATEGORY_URL,
        {
            "category_group_code": "PK6",
            "x": x,
            "y": y,
            "radius": radius,
            "sort": "distance",
            "size": 1,
        },
    )
    documents = payload.get("documents", []) or []
    if not documents:
        return None

    top = documents[0]
    return {
        "id": top.get("id"),
        "name": top.get("place_name"),
        "address": top.get("address_name"),
        "road_address": top.get("road_address_name"),
        "phone": top.get("phone"),
        "distance": top.get("distance"),
        "x": top.get("x"),
        "y": top.get("y"),
        "place_url": top.get("place_url"),
        "category": top.get("category_name"),
    }


def _extract_place(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "name": doc.get("place_name"),
        "address": doc.get("address_name"),
        "road_address": doc.get("road_address_name"),
        "phone": doc.get("phone"),
        "distance": doc.get("distance"),
        "x": doc.get("x"),
        "y": doc.get("y"),
        "place_url": doc.get("place_url"),
        "category": doc.get("category_name"),
    }


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        token = str(keyword or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    if not text or not keywords:
        return []
    hits: list[str] = []
    for keyword in keywords:
        if keyword and keyword in text:
            hits.append(keyword)
    return hits


def _score_place(
    place: Dict[str, Any],
    include_keywords: list[str],
    exclude_keywords: list[str],
    hard_exclude_category_keywords: list[str],
    hard_include_keywords: list[str],
) -> Dict[str, Any]:
    name = _normalize_text(place.get("name"))
    category = _normalize_text(place.get("category"))
    combined = " ".join(value for value in [name, category] if value).strip()

    include_name = _find_keywords(name, include_keywords)
    include_category = _find_keywords(category, include_keywords)
    exclude_name = _find_keywords(name, exclude_keywords)
    exclude_category = _find_keywords(category, exclude_keywords)

    hard_exclude_hits = _find_keywords(category, hard_exclude_category_keywords)
    hard_include_hits = _find_keywords(combined, hard_include_keywords)

    score = (
        2 * len(include_name)
        + 3 * len(include_category)
        - 3 * len(exclude_name)
        - 4 * len(exclude_category)
    )

    has_include = bool(include_name or include_category or hard_include_hits)
    return {
        "score": score,
        "has_include": has_include,
        "hard_exclude_hits": hard_exclude_hits,
        "hard_include_hits": hard_include_hits,
    }


def _parse_distance(value: Any, default: int = 10**9) -> int:
    try:
        parsed = int(float(value))
        return parsed if parsed >= 0 else default
    except Exception:
        return default


@router.get("/flowers")
def list_nearby_flowers(
    current_user: dict = Depends(get_current_user),
    radius: int = 3000,
    size: int = 30,
    include_parking: bool = False,
    parking_radius: int = 2000,
) -> Dict[str, Any]:
    username = current_user["user_name"]
    if not username:
        raise HTTPException(status_code=400, detail="Username required")

    record = _load_user(_user_path(username))
    address = _build_address(record)
    if not address:
        raise HTTPException(status_code=400, detail="User address is missing")

    address_payload = _request_kakao(KAKAO_ADDRESS_URL, {"query": address})
    documents = address_payload.get("documents", [])
    if not documents:
        raise HTTPException(status_code=404, detail="Address not found")

    top = documents[0]
    x = top.get("x")
    y = top.get("y")
    if not x or not y:
        raise HTTPException(status_code=404, detail="Address coordinates not found")

    radius_val = _clamp_int(radius, 0, 20000, 3000)
    size_val = _clamp_int(size, 1, 15, 15)
    parking_radius_val = _clamp_int(parking_radius, 0, 20000, 2000)

    search_keywords = _normalize_keywords(
        [
            "원예",
            "가드닝",
            "식물",
            "플랜트샵",
            "화분",
            "다육",
            "관엽",
            "분재",
            "조경",
            "꽃집",
        ]
    )
    include_keywords = _normalize_keywords(
        [
            "원예",
            "가드닝",
            "식물",
            "플랜트",
            "플랜트샵",
            "화분",
            "다육",
            "관엽",
            "분재",
            "허브",
            "테라리움",
            "정원",
            "수목",
            "잔디",
            "농자재",
            "조경",
            "plant",
            "garden",
            "botanical",
        ]
    )
    exclude_keywords = _normalize_keywords(
        [
            "플로리스트",
            "시공",
            "토목",
            "공사",
            "공사업",
            "리스",
            "웨딩",
            "이벤트꽃",
            "꽃바구니",
            "꽃선물",
            "flower",
            "bouquet",
            "해병대",
            "병원",
            "치료",
            "복지",
            "문화유적",
            "학습장",
            "정밀",
        ]
    )
    category_allow_keywords = _normalize_keywords(
        [
            "원예업",
            "나무,묘목",
            "원예용품",
            "꽃집,꽃배달"
        ]
    )
    category_block_keywords = _normalize_keywords([])
    hard_exclude_category_keywords = _normalize_keywords([])
    hard_include_keywords = _normalize_keywords(
        [
            "원예",
            "가드닝",
            "식물",
            "플랜트",
            "화분",
            "다육",
            "관엽",
            "묘목",
            "종묘",
            "분재",
            "허브",
            "테라리움",
            "정원",
            "수목",
            "농자재",
            "조경",
        ]
    )
    min_score = 2
    collected: Dict[str, Dict[str, Any]] = {}
    raw_count = 0
    filter_stats = {
        "category_excluded": 0,
        "category_blocked": 0,
        "hard_excluded": 0,
        "score_excluded": 0,
        "no_include_excluded": 0,
    }
    for keyword in search_keywords:
        keyword_payload = _request_kakao(
            KAKAO_KEYWORD_URL,
            {
                "query": keyword,
                "x": x,
                "y": y,
                "radius": radius_val,
                "sort": "distance",
                "size": size_val,
            },
        )
        documents = keyword_payload.get("documents", []) or []
        raw_count += len(documents)
        for doc in documents:
            item = _extract_place(doc)
            category_text = _normalize_text(item.get("category"))
            if category_allow_keywords and not _find_keywords(
                category_text, category_allow_keywords
            ):
                filter_stats["category_excluded"] += 1
                continue
            if category_block_keywords and _find_keywords(
                category_text, category_block_keywords
            ):
                filter_stats["category_blocked"] += 1
                continue
            score_info = _score_place(
                item,
                include_keywords,
                exclude_keywords,
                hard_exclude_category_keywords,
                hard_include_keywords,
            )
            if score_info.get("hard_exclude_hits") and not score_info.get(
                "hard_include_hits"
            ):
                filter_stats["hard_excluded"] += 1
                continue
            if score_info.get("score", 0) < min_score:
                filter_stats["score_excluded"] += 1
                continue
            if not score_info.get("has_include"):
                filter_stats["no_include_excluded"] += 1
                continue
            item_key = item.get("id") or f"{item.get('name')}|{item.get('address')}|{item.get('x')}|{item.get('y')}"
            if not item_key:
                continue
            existing = collected.get(item_key)
            if existing is None:
                collected[item_key] = item
            else:
                if _parse_distance(item.get("distance")) < _parse_distance(existing.get("distance")):
                    collected[item_key] = item

    items = list(collected.values())
    items.sort(key=lambda it: _parse_distance(it.get("distance")))
    if size_val:
        items = items[:size_val]

    if include_parking:
        for item in items:
            if not item.get("x") or not item.get("y"):
                item["parking"] = None
                continue
            try:
                item["parking"] = _find_nearest_parking(
                    item["x"], item["y"], parking_radius_val
                )
            except HTTPException:
                item["parking"] = None

    return {
        "ok": True,
        "address": address,
        "coord": {"x": x, "y": y},
        "radius": radius_val,
        "count": len(items),
        "items": items,
        "meta": {
            "search_keywords": search_keywords,
            "include_keywords": include_keywords,
            "exclude_keywords": exclude_keywords,
            "category_allow_keywords": category_allow_keywords,
            "category_block_keywords": category_block_keywords,
            "hard_exclude_category_keywords": hard_exclude_category_keywords,
            "hard_include_keywords": hard_include_keywords,
            "min_score": min_score,
            "raw_count": raw_count,
            "filter_stats": filter_stats,
        },
    }
