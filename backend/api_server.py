import os
import json
import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.config import RESULT_DIR, UPLOAD_DIR, PLANTS_DIR, ASSET_DIR

from app.solar.weather_client import AsosWeatherClient

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from app.db.redis_client import get_redis, get_redis_error
from app.db.mysql_client import get_mysql, get_mysql_error
from app.db.s3_client import ping_s3, get_s3_error, get_presigned_url

from app.api.chat_routes import router as chat_router
from app.api.diary_routes import router as diary_router
from app.api.login_routes import router as login_router
from app.api.plantboard_routes import router as plantboard_router
from app.api.map_routes import router as map_router
from app.api.tamagotchi_routes import router as tamagotchi_router

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class StaticCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if request.url.path.startswith("/results"):
            response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response


# ...
AUTH_UPLOAD_DIR = os.path.normpath(os.path.join(BASE_DIR, "app", "api", "uploads"))
AUTH_UPLOAD_MOUNT = "/auth-uploads"

# ✅ 디렉토리 보장 (config에서 경로만 만들고, 여기서도 안전하게 한번 더)
os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PLANTS_DIR, exist_ok=True)
os.makedirs(AUTH_UPLOAD_DIR, exist_ok=True)
os.makedirs(ASSET_DIR, exist_ok=True)

app = FastAPI()

app.add_middleware(StaticCORSMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 정적 파일 mount는 여기(api_server)에서만 한다 (chat_routes에 넣지 말기)
# ✅ 중복 mount 제거: /results는 1번만
app.mount("/results", StaticFiles(directory=RESULT_DIR), name="results")
app.mount("/plants", StaticFiles(directory=PLANTS_DIR), name="plants")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")
app.mount(AUTH_UPLOAD_MOUNT, StaticFiles(directory=AUTH_UPLOAD_DIR), name="auth-uploads")



# 라우터 등록 (All)
app.include_router(chat_router)
app.include_router(diary_router)
app.include_router(login_router)
app.include_router(plantboard_router)
app.include_router(map_router)
app.include_router(tamagotchi_router)

_plants_cache = {}
_plants_key_cache = {}

# Redis JSON keys in redisinsight_plants_v7.txt
PLANT_REDIS_KEY_MAP = {
    "name_ko": ["이름_한국어", "이름ko"],
    "name_en": ["이름_영어", "이름_en"],
    "family": ["과명"],
    "type": ["종류"],
    "size": ["크기_구분"],
    "growth_type": ["생육형태"],
    "growth_speed": ["생장속도"],
    "height_min_cm": ["생장높이_min_cm"],
    "height_max_cm": ["생장높이_max_cm"],
    "width_min_cm": ["생장너비_min_cm"],
    "width_max_cm": ["생장너비_max_cm"],
    "leaf_texture": ["잎_질감"],
    "leaf_color": ["잎_색"],
    "leaf_pattern": ["잎_무늬"],
    "leaf_gloss": ["잎_광택"],
    "flower_season": ["꽃_계절"],
    "flower_color": ["꽃_색"],
    "fruit_season": ["열매_계절"],
    "fruit_color": ["열매_색"],
    "light_requirement": ["광_요구도"],
    "light_lux": ["광_요구도_Lux", "광량"],
    "light_lux_min": ["최소_광량_Lux", "광량_min"],
    "light_lux_max": ["최대_광량_Lux", "광량_max"],
    "direct_light_tolerance": ["직사광_내성"],
    "direct_light_risk": ["직광_위험도"],
    "placement": ["권장_배치_공간"],
    "window_distance": ["권장_창문거리_구간"],
    "window_min_cm": ["최소_창문_거리_cm"],
    "window_max_cm": ["최대_창문_거리", "최대_창문_거리_cm"],
    "humidity_pref": ["습도_선호"],
    "temp_min_c": ["생육온도_min_C"],
    "temp_max_c": ["생육온도_max_C"],
    "winter_min_c": ["겨울최저온도_C"],
    "soil_ph": ["토양_pH"],
    "soil_drainage": ["토양_배수"],
    "fertilizer": ["비료_요구"],
    "water_spring": ["물주기_봄"],
    "water_summer": ["물주기_여름"],
    "water_fall": ["물주기_가을"],
    "water_winter": ["물주기_겨울"],
    "water_count_spring": ["물_횟수_봄"],
    "water_count_summer": ["물_횟수_여름"],
    "water_count_fall": ["물_횟수_가을"],
    "water_count_winter": ["물_횟수_겨울"],
    "care_level": ["관리_난이도"],
    "care_requirement": ["관리_요구도"],
    "scent_strength": ["향기_강도"],
    "style_tags": ["스타일_태그"],
    "functional_tags": ["기능성_태그"],
    "pests": ["병충해"],
    "allergy_notice": ["사람_알러지_주의"],
    "allergy_type": ["사람_알러지_유형"],
    "allergy_cause": ["사람_알러지_원인"],
    "allergy_symptom": ["사람_알러지_증상"],
    "pet_target": ["반려동물_대상"],
    "pet_symptom": ["반려동물_증상"],
    "pet_memo": ["반려동물_메모"],
    "kid_warning": ["어린이_주의"],
    "kid_risk_type": ["어린이_위험_유형"],
    "kid_safety_grade": ["어린이_안전_등급"],
    "fertilizer_cycle_spring_days": ["비료주기_일수_봄"],
    "fertilizer_cycle_summer_days": ["비료주기_일수_여름", "비료주기_일수__여름"],
    "fertilizer_cycle_fall_days": ["비료주기_일수_가을"],
    "fertilizer_cycle_winter_days": ["비료주기_일수_겨울"],
    "character": ["캐릭터"],
    "personality": ["성격"],
    "photo_count": ["사진_갯수"],
}


def _pick_first(raw: dict, keys: list):
    for key in keys:
        val = raw.get(key)
        if val is None or val == "" or val == []:
            continue
        return val
    return None


def _build_attrs(raw: dict) -> dict:
    attrs = {}
    for out_key, redis_keys in PLANT_REDIS_KEY_MAP.items():
        attrs[out_key] = _pick_first(raw, redis_keys)
    return attrs


def _decode_redis_text(value: Any, encoding: str = "utf-8") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            return value.decode(encoding, errors="replace")
    return str(value)


def _decode_redis_key(key: Any) -> str:
    return _decode_redis_text(key)


def _decode_redis_payload(payload: Any) -> Any:
    if isinstance(payload, bytes):
        return _decode_redis_text(payload)
    return payload


def _safe_json_loads(payload: Any) -> Any:
    payload = _decode_redis_payload(payload)
    if not isinstance(payload, str):
        return payload

    text = payload.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        return payload


def _get_scan_limit() -> int:
    raw = os.getenv("REDIS_PLANTS_SCAN_LIMIT", "").strip()
    try:
        return max(0, int(raw))
    except Exception:
        return 0


def _normalize_plant_id(key: str, prefix: str) -> str:
    if prefix and key.startswith(prefix):
        return key[len(prefix):]
    if key.startswith("plant:"):
        return key.split("plant:", 1)[1]
    return key


def _sort_plant_keys(keys, prefix: str) -> list:
    def _parse_int(key: str):
        key = _normalize_plant_id(key, prefix)
        try:
            return int(key)
        except Exception:
            return None

    parsed = [(_parse_int(k), k) for k in keys]
    if all(p[0] is not None for p in parsed):
        parsed.sort(key=lambda item: item[0])
        return [p[1] for p in parsed]
    return sorted(keys)


def _get_cached_keys(r, prefix: str, cache_ttl: int) -> list:
    cache_key = prefix or "__all__"
    cached = _plants_key_cache.get(cache_key)
    if cache_ttl and cached and (time.time() - cached["ts"] <= cache_ttl):
        return cached["keys"]

    ids_set = os.getenv("REDIS_PLANTS_ID_SET", "").strip() or "plants:ids"
    keys = []
    if ids_set:
        try:
            if r.exists(ids_set):
                keys = [_decode_redis_key(key) for key in r.smembers(ids_set)]
        except Exception:
            keys = []

    if keys:
        keys = _sort_plant_keys(keys, prefix)
        if cache_ttl:
            _plants_key_cache[cache_key] = {"ts": time.time(), "keys": keys}
        return keys

    cursor = 0
    scan_limit = _get_scan_limit()
    while True:
        cursor, batch = r.scan(cursor=cursor, match=f"{prefix}*" if prefix else None, count=1000)
        batch = [_decode_redis_key(key) for key in batch]
        keys.extend(batch)
        if scan_limit and len(keys) >= scan_limit:
            keys = keys[:scan_limit]
            break
        if cursor == 0:
            break

    if not prefix and ids_set:
        keys = [key for key in keys if key != ids_set]

    keys = _sort_plant_keys(keys, prefix)
    if cache_ttl:
        _plants_key_cache[cache_key] = {"ts": time.time(), "keys": keys}
    return keys


def _fetch_redis_json_items(r, keys: list, json_path: str) -> list:
    if not keys:
        return []
    keys = [_decode_redis_key(key) for key in keys]
    try:
        raw_items = r.execute_command("JSON.MGET", *keys, json_path)
    except Exception:
        raw_items = None

    if raw_items is None:
        try:
            pipe = r.pipeline()
            for key in keys:
                pipe.execute_command("JSON.GET", key, json_path)
            raw_items = pipe.execute()
        except Exception:
            pipe = r.pipeline()
            for key in keys:
                pipe.get(key)
            raw_items = pipe.execute()

    items = []
    for payload in raw_items:
        payload = _decode_redis_payload(payload)
        if payload is None:
            items.append(None)
            continue
        decoded = _safe_json_loads(payload)
        if isinstance(decoded, list) and len(decoded) == 1:
            decoded = decoded[0]
        items.append(decoded)
    return items


def _get_s3_settings() -> tuple[str, bool, str]:
    base_url = os.getenv("S3_PLANT_IMAGE_BASE_URL", "").strip().rstrip("/")
    use_presigned = os.getenv("S3_USE_PRESIGNED_URLS", "").strip().lower() in ("1", "true", "yes")
    prefix_path = os.getenv("S3_PLANT_IMAGE_PREFIX", "").strip().strip("/") or "plant_img"
    return base_url, use_presigned, prefix_path


def _s3_extract_key(value: str, base_url: str, prefix_path: str) -> str | None:
    if not value:
        return None
    val = value.strip()
    if not val:
        return None

    key = None
    if val.lower().startswith(("http://", "https://")):
        if base_url and val.startswith(base_url):
            remainder = val[len(base_url):].lstrip("/")
            if base_url.lower().endswith(prefix_path.lower()):
                key = f"{prefix_path}/{remainder}" if remainder else prefix_path
            else:
                key = remainder
        elif ".amazonaws.com/" in val:
            remainder = val.split(".amazonaws.com/", 1)[1]
            key = remainder.lstrip("/")
        else:
            return None
    else:
        key = val
        if base_url and val.startswith(base_url):
            key = val[len(base_url):].lstrip("/")

    if not key:
        return None
    if not key.lower().startswith(f"{prefix_path.lower()}/"):
        key = f"{prefix_path}/{key.lstrip('/')}"
    return key


def _s3_presign_value(value: str, base_url: str, prefix_path: str) -> str:
    key = _s3_extract_key(value, base_url, prefix_path)
    if not key:
        return value
    return get_presigned_url(key) or value


def _get_plant_image_ext_list() -> list[str]:
    # Project convention: plant images are stored only as .jpg.
    return [".jpg"]


def _build_filenames_for_index(plant_id: str, idx: int) -> list[str]:
    return [f"plant_{plant_id}_{idx}{ext}" for ext in _get_plant_image_ext_list()]


def _build_s3_candidate_keys(prefix_path: str, candidates: list[str]) -> list[str]:
    return [f"{prefix_path}/{name}" for name in candidates]


def _presign_candidate_keys(candidate_keys: list[str], include_all_fallbacks: bool = False) -> list[str]:
    if not candidate_keys:
        return []
    # Performance-first: skip S3 existence probes and sign directly.
    # Frontend already falls back across candidate URLs on image load errors.
    if include_all_fallbacks:
        signed = [get_presigned_url(key_path) for key_path in candidate_keys]
        return [url for url in signed if url]

    fallback = get_presigned_url(candidate_keys[0])
    return [fallback] if fallback else []


def _resolve_explicit_image_value(image: str, base_url: str, use_presigned: bool, prefix_path: str) -> str:
    if use_presigned:
        return _s3_presign_value(image, base_url, prefix_path)
    if image.lower().startswith(("http://", "https://")):
        return image
    if not base_url:
        return image

    prefix_token = f"{prefix_path.lower()}/"
    if image.lower().startswith(prefix_token) and base_url.lower().endswith(prefix_path.lower()):
        image = image[len(prefix_path) + 1:]
    image = image.lstrip("/")
    return f"{base_url}/{image}"


def _resolve_plant_image(raw: dict, key: str, prefix: str, attrs: dict | None = None):
    image = raw.get("image") or raw.get("이미지")
    base_url, use_presigned, prefix_path = _get_s3_settings()

    if isinstance(image, str) and image.strip():
        image = image.strip()
        return _resolve_explicit_image_value(image, base_url, use_presigned, prefix_path)

    if not base_url and not use_presigned:
        return None

    plant_id = _normalize_plant_id(key, prefix)
    if not plant_id:
        return None
    candidates = _build_filenames_for_index(plant_id, 1)
    if use_presigned:
        key_candidates = _build_s3_candidate_keys(prefix_path, candidates)
        urls = _presign_candidate_keys(key_candidates, include_all_fallbacks=False)
        return urls[0] if urls else None
    filename = candidates[0]
    return f"{base_url}/{filename}"


def _resolve_images_from_payload(images_raw, base_url: str, use_presigned: bool, prefix_path: str) -> list[str]:
    if not isinstance(images_raw, list):
        return []

    resolved = []
    for item in images_raw:
        if not isinstance(item, str) or not item.strip():
            continue
        item = item.strip()
        resolved.append(_resolve_explicit_image_value(item, base_url, use_presigned, prefix_path))
    return resolved


def _resolve_plant_images(raw: dict, key: str, prefix: str, attrs: dict | None = None) -> list:
    base_url, use_presigned, prefix_path = _get_s3_settings()
    if not base_url and not use_presigned:
        return []

    if attrs is None:
        attrs = _build_attrs(raw)

    image_count = attrs.get("photo_count")
    try:
        image_count = int(image_count)
        if image_count < 1:
            image_count = None
    except Exception:
        image_count = None

    images_raw = raw.get("images") or raw.get("이미지들")
    resolved_from_payload = _resolve_images_from_payload(images_raw, base_url, use_presigned, prefix_path)
    if resolved_from_payload:
        return resolved_from_payload

    max_images_raw = os.getenv("S3_PLANT_IMAGE_MAX", "").strip()
    try:
        max_images = max(1, min(int(max_images_raw), 12))
    except Exception:
        max_images = 4
    if image_count:
        max_images = min(max_images, image_count)

    plant_id = _normalize_plant_id(key, prefix)
    if not plant_id:
        return []

    if use_presigned:
        signed = []
        for idx in range(1, max_images + 1):
            candidates = _build_filenames_for_index(plant_id, idx)
            key_candidates = _build_s3_candidate_keys(prefix_path, candidates)
            signed.extend(_presign_candidate_keys(key_candidates, include_all_fallbacks=True))
        deduped = []
        seen = set()
        for url in signed:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped
    ext = _get_plant_image_ext_list()[0]
    filenames = [f"plant_{plant_id}_{idx}{ext}" for idx in range(1, max_images + 1)]
    return [f"{base_url}/{name}" for name in filenames]


def _normalize_plant_payload(raw, key: str, prefix: str) -> dict:
    key = _decode_redis_key(key)
    raw = _safe_json_loads(raw)
    if not isinstance(raw, dict):
        raw = {}

    def _join_list(val):
        if isinstance(val, list):
            return ", ".join([str(item) for item in val if item is not None])
        return val

    attrs = _build_attrs(raw)

    name_ko = attrs.get("name_ko")
    name_en = attrs.get("name_en")
    care_level = attrs.get("care_level")
    care_requirement = attrs.get("care_requirement")
    if care_level is None:
        care_level = raw.get("관리_난이도")
    if care_requirement is None:
        care_requirement = raw.get("관리_요구도")
    allergy_notice = attrs.get("allergy_notice")
    allergy_type = attrs.get("allergy_type")
    allergy_symptom = attrs.get("allergy_symptom")
    allergy_cause = attrs.get("allergy_cause")
    allergy = allergy_type or allergy_notice or allergy_symptom or allergy_cause

    pet_target = attrs.get("pet_target")
    pet_symptom = attrs.get("pet_symptom")
    pet_target_text = pet_target.strip() if isinstance(pet_target, str) else ""
    pet_symptom_text = pet_symptom.strip() if isinstance(pet_symptom, str) else ""
    # If symptom/target is explicitly "none", treat as safe.
    if pet_symptom_text in ("없음", "none", "None"):
        pet_safe = True
    elif pet_target_text in ("없음", "none", "None"):
        pet_safe = True
    else:
        # Otherwise keep binary classification (empty target list = safe, else caution).
        pet_safe = isinstance(pet_target, list) and len(pet_target) == 0

    light_lux = attrs.get("light_lux")
    light_min = attrs.get("light_lux_min")
    light_max = attrs.get("light_lux_max")

    if light_min is None:
        light_min = raw.get("광량_min")
    if light_max is None:
        light_max = raw.get("광량_max")

    if light_min is None and isinstance(raw.get("최소_광량_Lux"), (str, int, float)):
        light_min = raw.get("최소_광량_Lux")
    if light_max is None and isinstance(raw.get("최대_광량_Lux"), (str, int, float)):
        light_max = raw.get("최대_광량_Lux")

    if isinstance(light_lux, list) and light_lux:
        if light_min is None:
            light_min = light_lux[0]
        if light_max is None and len(light_lux) > 1:
            light_max = light_lux[-1]
        elif light_max is None and len(light_lux) == 1 and isinstance(light_lux[0], str) and "~" in light_lux[0]:
            parts = [part.strip() for part in light_lux[0].split("~", 1)]
            if parts and parts[0]:
                light_min = parts[0]
            if len(parts) > 1 and parts[1]:
                light_max = parts[1]
    elif light_max is None and isinstance(light_lux, str) and "~" in light_lux:
        parts = [part.strip() for part in light_lux.split("~", 1)]
        if light_min is None and parts and parts[0]:
            light_min = parts[0]
        if len(parts) > 1 and parts[1]:
            light_max = parts[1]

    light_min = _join_list(light_min)
    light_max = _join_list(light_max)

    placement = attrs.get("placement")
    placement = _join_list(placement)

    image = _resolve_plant_image(raw, key, prefix, attrs=attrs)
    images = _resolve_plant_images(raw, key, prefix, attrs=attrs)
    if image:
        if image not in images:
            images = [image, *images]

    return {
        "id": _normalize_plant_id(key, prefix),
        "name": name_ko or name_en or key,
        "name_ko": name_ko,
        "name_en": name_en,
        "type": attrs.get("type"),
        "size": attrs.get("size"),
        "light_min": light_min,
        "light_max": light_max,
        "light_requirement": attrs.get("light_requirement"),
        "light_lux": light_lux,
        "direct_light_tolerance": attrs.get("direct_light_tolerance"),
        "placement": placement,
        "care": care_level,
        "care_difficulty": care_level,
        "care_effort": care_requirement,
        "allergy": allergy,
        "pet_safe": pet_safe,
        "character": attrs.get("character"),
        "personality": attrs.get("personality"),
        "photo_count": attrs.get("photo_count"),
        "image": image,
        "images": images,
        "attrs": attrs,
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/debug/redis")
def redis_debug():
    r = get_redis()
    if not r:
        return {"ok": False, "reason": "no_connection", "error": get_redis_error()}
    try:
        r.ping()
    except Exception:
        return {"ok": False, "reason": "ping_failed"}

    prefix = os.getenv("REDIS_PLANTS_PREFIX", "").strip()
    ids_set = os.getenv("REDIS_PLANTS_ID_SET", "").strip() or "plants:ids"
    count = None
    if prefix:
        try:
            if ids_set and r.exists(ids_set):
                count = r.scard(ids_set)
            else:
                cursor = 0
                count = 0
                limit = 5000
                scan_limit = _get_scan_limit()
                if scan_limit:
                    limit = min(limit, scan_limit)
                while True:
                    cursor, keys = r.scan(cursor=cursor, match=f"{prefix}*", count=200)
                    count += len(keys)
                    if cursor == 0 or count >= limit:
                        break
        except Exception:
            count = None

    sample_name = None
    if prefix:
        try:
            sample_key = f"{prefix}1"
            raw = r.execute_command("JSON.GET", sample_key, "$.이름_한국어")
            if raw is None:
                raw = r.execute_command("JSON.GET", sample_key, "$.이름_영어")
            sample_name = _safe_json_loads(raw)
            if isinstance(sample_name, list) and len(sample_name) == 1:
                sample_name = sample_name[0]
        except Exception:
            sample_name = None

    return {
        "ok": True,
        "prefix": prefix or None,
        "key_count": count,
        "sample_name": sample_name,
    }


@app.get("/api/plants")
def list_plants(cursor: int = 0, limit: int = 24, offset: int | None = None):
    cache_sec = os.getenv("REDIS_PLANTS_CACHE_SEC", "").strip()
    try:
        cache_ttl = max(0, int(cache_sec))
    except Exception:
        cache_ttl = 0

    r = get_redis()
    if not r:
        return {
            "ok": False,
            "items": [],
            "next_cursor": 0,
            "reason": "no_connection",
            "error": get_redis_error(),
        }

    prefix = os.getenv("REDIS_PLANTS_PREFIX", "").strip()
    json_path = os.getenv("REDIS_PLANTS_JSON_PATH", "$").strip() or "$"

    try:
        scan_cursor = max(int(cursor), 0)
    except Exception:
        scan_cursor = 0

    try:
        limit_val = max(1, min(int(limit), 100))
    except Exception:
        limit_val = 24

    if offset is not None:
        try:
            offset_val = max(0, int(offset))
        except Exception:
            offset_val = 0

        cache_key = ("offset", offset_val, limit_val)
        if cache_ttl:
            cached = _plants_cache.get(cache_key)
            if cached and (time.time() - cached["ts"] <= cache_ttl):
                return cached["payload"]

        keys = _get_cached_keys(r, prefix, cache_ttl)
        total = len(keys)
        slice_keys = keys[offset_val: offset_val + limit_val]
        items = []
        if slice_keys:
            raw_items = _fetch_redis_json_items(r, slice_keys, json_path)
            for key, decoded in zip(slice_keys, raw_items):
                if decoded is None:
                    continue
                items.append(_normalize_plant_payload(decoded, key, prefix))

        next_offset = offset_val + limit_val
        payload = {
            "ok": True,
            "items": items,
            "next_offset": next_offset if next_offset < total else None,
            "total": total,
        }
    else:
        cache_key = ("cursor", scan_cursor, limit_val)
        if cache_ttl:
            cached = _plants_cache.get(cache_key)
            if cached and (time.time() - cached["ts"] <= cache_ttl):
                return cached["payload"]

        items = []
        while len(items) < limit_val:
            scan_cursor, keys = r.scan(
                cursor=scan_cursor,
                match=f"{prefix}*" if prefix else None,
                count=max(limit_val * 2, 50),
            )
            keys = [_decode_redis_key(key) for key in keys]
            if keys:
                raw_items = _fetch_redis_json_items(r, keys, json_path)
                for key, decoded in zip(keys, raw_items):
                    if decoded is None:
                        continue
                    items.append(_normalize_plant_payload(decoded, key, prefix))
                    if len(items) >= limit_val:
                        break

            if scan_cursor == 0:
                break

        payload = {"ok": True, "items": items, "next_cursor": scan_cursor}
    if cache_ttl:
        _plants_cache[cache_key] = {"ts": time.time(), "payload": payload}
    return payload


@app.get("/debug/mysql")
def mysql_debug():
    conn = get_mysql()
    if not conn:
        return {"ok": False, "reason": "no_connection", "error": get_mysql_error()}
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return {"ok": False, "reason": "ping_failed"}
    return {"ok": True}


@app.get("/debug/s3")
def s3_debug():
    ok = ping_s3()
    if not ok:
        return {"ok": False, "error": get_s3_error()}
    return {"ok": True}
