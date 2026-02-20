from __future__ import annotations

import os, json, time, random, uuid, pathlib, glob, inspect, hashlib, requests, shutil
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageEnhance

from fastapi import UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from urllib.parse import urlparse

from app.cv.pipeline import run_pipeline, list_71765_scenes
from app.cv.space_classifier import classify_space
from app.cv.scene_room_infer import infer_room_type_from_scene_json, load_scene_json
from app.cv.scene_catalog import build_room_groups, DEFAULT_SCENE_ROOT, pick_scene_for_room

from app.config import BASE_DIR, RESULT_DIR, RESULT_JSON_LATEST, UPLOAD_DIR, ASSET_DIR
from app.llm.image_edit import composite_plant_on_original
from app.llm.gemini.gemini_image_edit import gemini_inpaint_with_reference
from app.solar.weather_client import AsosWeatherClient
from app.reco.recommender import recommend_for_analysis

from .chat_session import _get_or_create_sid, _json_with_sid, _get_client_id
from .chat_storage import get_user_ctx, set_user_ctx
from .chat_utils import cache_bust_url, to_results_url, extract_best_point, safe_float

load_dotenv()
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

weather_client = AsosWeatherClient()

# =========================
# Models
# =========================

class AnalyzeBody(BaseModel):
    filters: Dict[str, Any] = Field(default_factory=dict)
    meta: Optional[Dict[str, Any]] = None

class RecommendBody(BaseModel):
    filters: Dict[str, Any] = Field(default_factory=dict)
    meta: Optional[Dict[str, Any]] = None


async def handle_chat_recommend(request: Request, body: RecommendBody) -> JSONResponse:
    sid, sid_is_new = _get_or_create_sid(request)
    key = sid

    # 1) 기존 분석 결과 로드
    latest_json = os.path.join(RESULT_DIR, "result_latest.json")
    if not os.path.exists(latest_json):
        return _json_with_sid(
            {"ok": False, "messages": [{"type": "text", "text": "저장된 분석 결과가 없습니다. 먼저 analyze를 실행하세요."}]},
            sid, sid_is_new
        )

    try:
        with open(latest_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return _json_with_sid(
            {"ok": False, "messages": [{"type": "text", "text": f"result_latest.json 읽기 실패: {e}"}]},
            sid, sid_is_new
        )

    # 2) 필터 저장 + 추천만 재실행
    user_filters = body.filters if isinstance(body.filters, dict) else {}
    set_user_ctx(key, {"filters": user_filters}, ttl_sec=60 * 60 * 6)

    data = recommend_for_analysis(data, user_filters=user_filters)

    # 3) 저장
    try:
        with open(latest_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[WARN] overwrite latest_json failed:", e)

    # 4) 프론트가 쓰기 쉬운 응답
    return _json_with_sid(
        {
            "ok": True,
            "messages": [{"type": "text", "text": "✅ 필터가 적용되어 추천 결과를 갱신했습니다."}],
            "cv_result": data,
        },
        sid, sid_is_new
    )

def _pick_scene_for_room_compat(room_type: str, seed: Optional[str] = None):
    """
    room_type(거실/침실/주방/욕실 또는 영어 변형)를 받아서
    DEFAULT_SCENE_ROOT 기준으로 scene_id를 하나 뽑아 반환한다. (없으면 None)
    """
    rt = (room_type or "").strip()
    rt_key = rt.replace(" ", "").lower()

    rt_map = {
        "거실": "거실", "침실": "침실", "주방": "주방", "욕실": "욕실",
        "livingroom": "거실", "living_room": "거실", "living": "거실",
        "bedroom": "침실", "bed_room": "침실",
        "kitchen": "주방",
        "bathroom": "욕실", "bath_room": "욕실", "restroom": "욕실", "toilet": "욕실",
    }
    room_kor = rt_map.get(rt, rt_map.get(rt_key, rt))

    # ✅ groups를 반드시 dict로 만든 뒤 pick_scene_for_room(groups, room_type)로만 호출
    try:
        groups = build_room_groups(DEFAULT_SCENE_ROOT)
        if not isinstance(groups, dict):
            print("[pick_scene_compat][WARN] groups is not dict:", type(groups))
            return None

        picked = pick_scene_for_room(groups, room_kor, seed=seed)
        return picked
    except Exception as e:
        print("[pick_scene_compat][WARN] build/pick failed:", e)
        return None



# ✅ room groups(options)만
def get_scenes():
    groups = build_room_groups(DEFAULT_SCENE_ROOT)

    options = []
    for k in ["거실", "침실", "주방", "욕실"]:
        cnt = len(groups.get(k) or [])
        options.append({"key": k, "label": f"{k} ({cnt})"})

    return {"ok": True, "type": "room_groups", "options": options}

# ✅ 전체 scene 리스트(라벨 포함) 반환
def get_scenes_all():
    root = pathlib.Path(DEFAULT_SCENE_ROOT)
    scenes = list_71765_scenes()

    out = []
    for sid in scenes:
        scene_json = load_scene_json(root, sid)
        if not scene_json:
            continue

        room_type = infer_room_type_from_scene_json(scene_json)

        meta = scene_json.get("metadata", {}) if isinstance(scene_json, dict) else {}
        space_subclass = meta.get("space_subclass") or ""
        space_detail = meta.get("space_detail") or ""

        label = f"{space_subclass} / {room_type}".strip(" /")
        if space_detail:
            label += f" ({space_detail})"

        out.append({"id": sid, "label": label})

    return {"ok": True, "scenes": out}

def get_results():
    """
    프론트가 /api/chat/results로 받아갈 '최신 결과 메타'를 반환.
    필요하면 형식은 프론트에 맞춰 확장.
    """
    latest_json_path = str(RESULT_JSON_LATEST)
    exists = os.path.exists(latest_json_path)

    # 최신 결과 이미지들(예: result_latest_*.png) 목록
    files = sorted(
        [os.path.basename(p) for p in glob.glob(os.path.join(str(RESULT_DIR), "result_latest_*.png"))]
    )

    return JSONResponse({
        "ok": True,
        "latest_json_exists": exists,
        "latest_json": os.path.basename(latest_json_path),
        "latest_images": files,
    })

# =========================
# Detail text -> constraints (원본 유지)
# =========================
def parse_detail_text_to_constraints(text: str) -> Dict[str, Any]:
    t = (text or "").strip().lower()

    placement = None
    if any(k in t for k in ["테이블", "상판", "선반", "책상"]):
        placement = "table"
    elif any(k in t for k in ["바닥", "플로어", "바닥에"]):
        placement = "floor"

    light_pref = None
    if any(k in t for k in ["햇빛없", "빛없", "어두", "그늘", "저광량"]):
        light_pref = "low"
    elif any(k in t for k in ["햇빛많", "직사광", "고광량", "밝은곳"]):
        light_pref = "high"
    elif any(k in t for k in ["반그늘", "중간", "간접광", "중광량"]):
        light_pref = "medium"

    pet = None
    if any(k in t for k in ["반려묘", "고양이", "강아지", "반려동물"]):
        pet = True

    size = None
    if any(k in t for k in ["큰", "대형", "키큰"]):
        size = "large"
    elif any(k in t for k in ["작은", "소형", "미니"]):
        size = "small"
    elif any(k in t for k in ["중형", "적당한"]):
        size = "medium"

    return {
        "raw_text": text,
        "placement": placement,
        "light_pref": light_pref,
        "size_pref": size,
        "pet_hint": pet,
    }


# =========================
# Gemini prompt builder (원본 유지)
# =========================
def _prompt_for_edit(best_point: Any, spot_usage: str, plant_name: Optional[str] = None) -> str:
    plant_text = plant_name or "실내 화분 식물"

    base_rules = (
        "원본 방 사진은 절대 변경하지 마세요. "
        "가구/창문/바닥/벽/조명/원근/구도는 그대로 유지하세요. "
        "초록색 점으로 표시된 위치에서 반경 40픽셀 이내에만 식물을 배치하세요. "
        "식물은 현실적인 크기와 그림자, 접지감을 가지게 하세요. "
        "다른 물체를 추가/삭제하지 마세요. "
        f"(추천 좌표: {best_point}) "
    )

    if spot_usage == "floor_large":
        mode_rules = (
            f"{plant_text}를 바닥(FLOOR)에 설치하세요. "
            "테이블, 선반, 가구 위에 두지 마세요. "
            "중형~대형 화분으로 표현하세요 (높이 40~90cm). "
        )
    elif spot_usage == "table_small":
        mode_rules = (
            f"{plant_text}를 테이블 또는 상판(TABLETOP)에 올려주세요. "
            "바닥에 두지 마세요. "
            "소형 화분으로 표현하세요 (높이 15~35cm). "
        )
    elif spot_usage == "low_light":
        mode_rules = (
            f"{plant_text}를 저광량 환경에 적합하게 배치하세요. "
            "강한 햇빛을 가정하지 마세요. "
            "소형~중형 화분으로 표현하세요. "
        )
    else:
        mode_rules = f"{plant_text}를 가장 자연스럽고 안전한 방식으로 소형 화분으로 배치하세요. "

    return base_rules + mode_rules


# =========================
# SOLAR helpers (원본 유지)
# =========================
def _solar_summary_from_asos(weather_res: Dict[str, Any]) -> Dict[str, Any]:
    """
    AsosWeatherClient에서 받은 단일 실측 데이터를
    기존 시스템이 이해하는 morning/noon/evening 구조로 변환합니다.
    """
    out = {
        "ok": False,
        "times": {"morning": 0.0, "noon": 0.0, "evening": 0.0},
        "source": "kma_asos",
        "reason": "",
    }

    if not weather_res:
        out["reason"] = "weather_data_empty"
        return out

    # ASOS 실측값 가져오기
    try:
        val = float(weather_res.get("solar_radiation") or 0.0)
    except (ValueError, TypeError):
        val = 0.0

    # 시간 파싱 보강 (observed_at 대응)
    obs_time = str(weather_res.get("observed_at") or "")
    hh = 12 # 기본값

    try:
        if " " in obs_time:
            # "2026-02-03 12" 형식 대응
            hh = int(obs_time.split()[-1].split(":")[0])
        elif len(obs_time) >= 10:
            # "202602031200" 형식 대응 (뒤에서 4~2번째 자리)
            hh = int(obs_time[-4:-2])
    except Exception:
        hh = 12 # 에러 시 정오로 간주

    # 현재 실측된 값을 해당 시간대에 할당
    if 6 <= hh <= 10:
        out["times"]["morning"] = val
    elif 11 <= hh <= 15:
        out["times"]["noon"] = val
    elif 16 <= hh <= 19:
        out["times"]["evening"] = val
    else:
        # 야간(0.0)이거나 범위를 벗어나면 noon에 할당하여 가중치 0으로 처리
        out["times"]["noon"] = val

    out["ok"] = True
    return out


def _normalize_3(t: Dict[str, Optional[float]]) -> Dict[str, float]:
    m = safe_float(t.get("morning")) or 0.0
    n = safe_float(t.get("noon")) or 0.0
    e = safe_float(t.get("evening")) or 0.0
    mx = max(m, n, e)
    if mx <= 0:
        return {"morning": 1.0, "noon": 1.0, "evening": 1.0}
    return {"morning": m / mx, "noon": n / mx, "evening": e / mx}


def _clip01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def _apply_solar_to_spots(data: Dict[str, Any], solar_summary: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data
    spots = data.get("spots")
    if not isinstance(spots, list) or not spots:
        return data

    solar_times = (solar_summary or {}).get("times") if isinstance(solar_summary, dict) else None
    if not isinstance(solar_times, dict):
        return data

    scale = _normalize_3(solar_times)

    for s in spots:
        if not isinstance(s, dict):
            continue

        feats = s.get("features")
        if isinstance(feats, dict):
            times = feats.get("times")
            if isinstance(times, dict):
                if "times_cv" not in feats:
                    feats["times_cv"] = dict(times)

                feats["times"] = {
                    "morning": _clip01((safe_float(times.get("morning")) or 0.0) * scale["morning"]),
                    "noon": _clip01((safe_float(times.get("noon")) or 0.0) * scale["noon"]),
                    "evening": _clip01((safe_float(times.get("evening")) or 0.0) * scale["evening"]),
                }

        lp = s.get("light_profile")
        if isinstance(lp, dict):
            lpt = lp.get("times")
            if isinstance(lpt, dict):
                if "times_cv" not in lp:
                    lp["times_cv"] = dict(lpt)

                new_lpt = {
                    "morning": _clip01((safe_float(lpt.get("morning")) or 0.0) * scale["morning"]),
                    "noon": _clip01((safe_float(lpt.get("noon")) or 0.0) * scale["noon"]),
                    "evening": _clip01((safe_float(lpt.get("evening")) or 0.0) * scale["evening"]),
                }
                lp["times"] = new_lpt
                lp["bias"] = max(new_lpt.items(), key=lambda kv: kv[1])[0] if new_lpt else "unknown"

    data["solar_apply"] = {
        "ok": True,
        "scale": scale,
        "note": "features.times and light_profile.times multiplied by normalized solar_summary.times; originals kept in *_times_cv",
    }
    return data

# =========================
# /api/chat (POST) handler
# =========================
async def handle_chat_post(request: Request) -> JSONResponse:
    # 1/2/3 페이지 분리 이후, chat 텍스트 플로우는 사용하지 않음.
    # (프론트가 실수로 호출해도 깨지지 않도록 최소 응답만 반환)
    sid, sid_is_new = _get_or_create_sid(request)
    return _json_with_sid(
        {
            "ok": True,
            "deprecated": True,
            "messages": [
                {"type": "text", "text": "이 엔드포인트(/api/chat POST)는 더 이상 사용하지 않습니다. /api/chat/image 및 /api/chat/analyze를 사용하세요."}
            ],
        },
        sid,
        sid_is_new,
    )


def _run_pipeline_compat(save_path: str, user_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    run_pipeline 파라미터명이 환경마다 달라서 scene_id가 씹히는 문제를 막기 위한 호환 호출.
    - user_opts / opts / options / kwargs 등 다양한 케이스를 순서대로 시도한다.
    """
    user_opts = user_opts or {}

    # 1) 시그니처 기반으로 가능한 키워드만 시도
    try:
        sig = inspect.signature(run_pipeline)
        params = sig.parameters

        if "user_opts" in params:
            return run_pipeline(save_path, user_opts=user_opts)
        if "opts" in params:
            return run_pipeline(save_path, opts=user_opts)
        if "options" in params:
            return run_pipeline(save_path, options=user_opts)
        if "config" in params:
            # 일부 구현에서 config dict를 받는 경우가 있음
            return run_pipeline(save_path, config=user_opts)
    except Exception:
        # signature 조회 실패하면 아래 fallback들로 간다
        pass

    # 2) 키워드 시도(실패하면 다음으로)
    try:
        return run_pipeline(save_path, user_opts=user_opts)
    except TypeError:
        pass
    try:
        return run_pipeline(save_path, opts=user_opts)
    except TypeError:
        pass
    try:
        return run_pipeline(save_path, options=user_opts)
    except TypeError:
        pass

    # 3) 최후 fallback: opts를 못 받으면 그냥 호출 (단, 이 경우 scene_id 반영 불가)
    return run_pipeline(save_path)

# =========================
# /api/chat/image handler (UPLOAD + ROOM ONLY)
# =========================
async def handle_chat_image(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    image: Optional[UploadFile] = File(None),
    meta: Optional[str] = Form(None),
    scene_id: Optional[str] = Form(None),
    room_type: Optional[str] = Form(None),
) -> JSONResponse:
    sid, sid_is_new = _get_or_create_sid(request)
    key = sid
    cid = _get_client_id(request) or sid
    # cid = sid

    upload: Optional[UploadFile] = None
    if files and len(files) > 0:
        upload = files[0]
    elif image is not None:
        upload = image

    if upload is None:
        return _json_with_sid(
            {
                "ok": False,
                "messages": [{"type": "text", "text": "업로드 파일이 없습니다."}],
            },
            sid,
            sid_is_new,
        )

    # 1) 저장
    orig_name = upload.filename or "upload.jpg"
    ext = pathlib.Path(orig_name).suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, filename)

    content = await upload.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # ctx에 무조건 저장 (2번에서 analyze가 이걸 씀)
    set_user_ctx(key, {"last_image_path": save_path}, ttl_sec=60 * 60 * 6)

    # meta도 ctx에 저장 (태양광/좌표용)
    if meta:
        m = meta
        try:
            # meta가 JSON 문자열이면 dict로 저장
            if isinstance(m, str) and m.strip().startswith("{"):
                m = json.loads(m)
        except Exception:
            m = meta  # 파싱 실패 시 원문 유지
        set_user_ctx(key, {"meta": m}, ttl_sec=60 * 60 * 6)

    # 2) room_type/scene_id 확정 로직
    user_opts: Dict[str, Any] = {}

    # (A) 사용자가 scene_id를 직접 보내면 최우선
    if scene_id:
        user_opts["scene_id"] = scene_id
        set_user_ctx(key, {"scene_id": scene_id}, ttl_sec=60 * 60 * 6)
        return _json_with_sid(
            {
                "ok": True,
                "need_room_type": False,
                "next": "preferences",
                "saved_image": filename,
            },
            sid,
            sid_is_new,
        )

    # (B) room_type이 왔다면 -> scene_id 픽해서 확정
    if room_type:
        try:
            picked = _pick_scene_for_room_compat(room_type)
        except Exception as e:
            return _json_with_sid(
                {"ok": False, "messages": [{"type": "text", "text": f"room_type 처리 오류: {e}"}]},
                sid,
                sid_is_new,
            )

        if not picked:
            # ✅ 강제 진행: room_type은 저장하고 scene_id 없이도 survey/analyze로 넘긴다
            set_user_ctx(key, {"room_type": str(room_type).strip()}, ttl_sec=60 * 60 * 6)

            return _json_with_sid(
                {
                    "ok": True,
                    "need_room_type": False,
                    "next": "preferences",
                    "room_type": str(room_type).strip(),
                    "scene_id": None,
                    "saved_image": filename,
                    "note": "scene_id_pick_failed_but_forced_next",
                },
                sid,
                sid_is_new,
            )

        # room_type -> scene_id 확정 저장
        set_user_ctx(key, {"room_type": str(room_type).strip(), "scene_id": picked}, ttl_sec=60 * 60 * 6)

        return _json_with_sid(
            {
                "ok": True,
                "need_room_type": False,
                "next": "preferences",
                "room_type": str(room_type).strip(),
                "scene_id": picked,
                "saved_image": filename,
            },
            sid,
            sid_is_new,
        )

    # (C) 아무것도 안 왔으면 -> 일단 pipeline 1회 돌려보고
    # scene_required 뜨면 room_type 선택 요구, 아니면 자동으로 preferences로
    try:
        out = _run_pipeline_compat(save_path, user_opts={})  # scene_id 없이 1회
    except Exception as e:
        return _json_with_sid(
            {"ok": False, "messages": [{"type": "text", "text": f"분석(1차) 중 오류: {e}"}]},
            sid,
            sid_is_new,
        )

    scene_info = out.get("scene") if isinstance(out, dict) else None
    if isinstance(scene_info, dict) and scene_info.get("reason") == "scene_required":
        return _json_with_sid(
            {
                "ok": True,
                "need_room_type": True,
                "payload": {"type": "room_type_required", "options": ["거실", "침실", "주방", "욕실"]},
                "saved_image": filename,
            },
            sid,
            sid_is_new,
        )

    # ✅ scene_required가 아니더라도 pipeline이 scene을 자동 확정했으면 ctx에 저장
    # (out 구조가 달라도 안전하게 key 여러 개 시도)
    if isinstance(out, dict):
        sc = out.get("scene")
        chosen = None
        if isinstance(sc, dict):
            chosen = sc.get("chosen") or sc.get("scene_id") or sc.get("id")
        if isinstance(chosen, str) and chosen.strip():
            set_user_ctx(key, {"scene_id": chosen.strip()}, ttl_sec=60 * 60 * 6)

    # scene_required가 아니면 그냥 다음 단계로
    return _json_with_sid(
        {
            "ok": True,
            "need_room_type": False,
            "next": "preferences",
            "saved_image": filename,
        },
        sid,
        sid_is_new,
    )

# =========================
# render_plan → best_point 강제 반영 헬퍼
# =========================
def _best_point_from_spot(s: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(s, dict):
        return {}
    pt = None
    for k in ["pt", "point", "xy", "center"]:
        v = s.get(k)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            pt = [float(v[0]), float(v[1])]
            break
        if isinstance(v, dict) and "x" in v and "y" in v:
            pt = [float(v["x"]), float(v["y"])]
            break
    if pt is None:
        feats = s.get("features")
        if isinstance(feats, dict):
            v = feats.get("pt") or feats.get("xy") or feats.get("center")
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                pt = [float(v[0]), float(v[1])]
            elif isinstance(v, dict) and "x" in v and "y" in v:
                pt = [float(v["x"]), float(v["y"])]
    return {"pt": pt, "spot_index": s.get("spot_index")}

def _choose_spot_by_render_plan(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    spots = data.get("spots")
    if not isinstance(spots, list) or not spots:
        return None

    # 1) render_plan이 있으면 그걸 최우선
    rp = data.get("render_plan")
    if isinstance(rp, dict):
        idxs = rp.get("spot_indexes")
        if isinstance(idxs, list) and idxs:
            try:
                i = int(idxs[0])
                if 0 <= i < len(spots) and isinstance(spots[i], dict):
                    return spots[i]
            except Exception:
                pass

    # 2) render_plan이 없거나 깨졌으면 기존 best_spot
    bs = data.get("best_spot")
    if isinstance(bs, dict):
        return bs

    # 3) 최후: 첫 spot
    return spots[0] if isinstance(spots[0], dict) else None


def _norm_size_token(v: Any) -> str:
    s = (str(v).strip().lower() if v is not None else "")
    if s in ("", "없음", "해당없음", "none"):
        return ""
    if s in ("소형", "작은", "미니", "small"):
        return "small"
    if s in ("중형", "보통", "medium"):
        return "medium"
    if s in ("대형", "큰", "large"):
        return "large"
    return s


def _is_small_from_filters(data: Dict[str, Any], user_filters: Dict[str, Any]) -> bool:
    size_pref = ""
    if isinstance(user_filters, dict):
        for k in ("size_pref", "size", "plant_size", "pot_size", "plantSize", "sizePref", "식물크기"):

            t = _norm_size_token(user_filters.get(k))
            if t:
                size_pref = t
                break

    if not size_pref and isinstance(data.get("constraints"), dict):
        size_pref = _norm_size_token(data["constraints"].get("size_pref"))

    return (size_pref == "small")


def _get_img_wh(data: Dict[str, Any]) -> tuple[int, int]:
    w = int(data.get("image_w") or data.get("w") or 1248)
    h = int(data.get("image_h") or data.get("h") or 832)
    return w, h


def _ensure_fixed_3_spots(data: Dict[str, Any]) -> List[int]:
    """
    CV spots가 망가져도 무조건 3개 spot index가 나오도록 하드코딩으로 보장한다.
    - 기존 spots가 있으면 최대한 활용
    - 부족하면 synthetic spot을 추가해서 3개를 채움
    """
    if not isinstance(data, dict):
        return [0, 1, 2]

    spots = data.get("spots")
    if not isinstance(spots, list):
        spots = []
        data["spots"] = spots

    w, h = _get_img_wh(data)

    def _clamp_pt(x: float, y: float) -> List[float]:
        x = max(10.0, min(float(w) - 10.0, float(x)))
        y = max(10.0, min(float(h) - 10.0, float(y)))
        return [x, y]

    def _has_pt(s: Any) -> bool:
        if not isinstance(s, dict):
            return False
        pt = s.get("pt")
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            return True
        feats = s.get("features")
        if isinstance(feats, dict):
            pt2 = feats.get("pt") or feats.get("center") or feats.get("xy")
            if isinstance(pt2, (list, tuple)) and len(pt2) >= 2:
                return True
        return False

    def _ensure_pt(s: Dict[str, Any]):
        # pt가 없으면 적당히 만들어 줌
        if _has_pt(s):
            # pt 값이 있으면 클램프만
            pt = s.get("pt")
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                s["pt"] = _clamp_pt(pt[0], pt[1])
            feats = s.get("features")
            if isinstance(feats, dict):
                pt2 = feats.get("pt") or feats.get("center") or feats.get("xy")
                if isinstance(pt2, (list, tuple)) and len(pt2) >= 2:
                    feats["pt"] = _clamp_pt(pt2[0], pt2[1])
            return

        # 없으면 하드코딩으로 하나 생성
        s["pt"] = _clamp_pt(w * 0.55, h * 0.75)
        s.setdefault("features", {})
        if isinstance(s["features"], dict):
            s["features"]["pt"] = list(s["pt"])
            s["features"]["center"] = list(s["pt"])

    # 1) 기존 spot들 중 pt 있는 애들 우선 3개 수집
    idxs: List[int] = []
    for i, s in enumerate(spots):
        if not isinstance(s, dict):
            continue
        _ensure_pt(s)
        idxs.append(i)
        if len(idxs) >= 3:
            break

    # 2) 부족하면 synthetic 3개 위치로 채움 (서로 다른 곳)
    #    (바닥 3개 고정 위치: 좌/중/우)
    target_pts = [
        _clamp_pt(w * 0.25, h * 0.82),
        _clamp_pt(w * 0.55, h * 0.80),
        _clamp_pt(w * 0.82, h * 0.83),
    ]

    while len(idxs) < 3:
        pt = target_pts[len(idxs)]
        new_idx = len(spots)
        spots.append({
            "spot_index": new_idx,
            "surface": "floor",
            "synthetic": True,
            "score": 1.0,
            "pt": pt,
            "features": {"pt": list(pt), "center": list(pt)},
        })
        idxs.append(new_idx)

    data["spots"] = spots
    return idxs

def _make_mask_from_point(
    w: int,
    h: int,
    pt: List[float],
    box_w: int = 240,
    box_h: int = 520,
    bottom_pad: int = 18,   # ✅ 바닥 아래로는 아주 조금만 열어줌
    feather: int = 6,
) -> Image.Image:
    """
    ✅ pt를 '바닥 접지점(화분 바닥 닿는 지점)'으로 가정하고,
    마스크를 위로 크게, 아래로는 아주 조금만 열어준다.
    => 바닥을 칠하는 "흰 원형판" 확률이 확 줄어듦.
    """
    x, y = float(pt[0]), float(pt[1])

    half_w = box_w / 2.0

    left   = max(0, int(x - half_w))
    right  = min(w, int(x + half_w))

    # ✅ bottom 정렬: pt가 마스크의 바닥쪽
    bottom = min(h, int(y + bottom_pad))
    top    = max(0, int(bottom - box_h))

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    radius = max(14, int(min(box_w, box_h) * 0.18))
    draw.rounded_rectangle([left, top, right, bottom], radius=radius, fill=255)

    if feather and feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))

    return mask

def _save_mask_for_spot(
    room_path: str,
    pt: List[float],
    out_path: str,
    box_w: int = 240,
    box_h: int = 520,
    bottom_pad: int = 12,
    feather: int = 6,
) -> str:
    room = Image.open(room_path)
    w, h = room.size
    mask = _make_mask_from_point(
        w, h, pt,
        box_w=box_w,
        box_h=box_h,
        bottom_pad=bottom_pad,
        feather=feather,
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    mask.save(out_path)
    return out_path



def _verify_outside_mask_identical(room_path: str, out_path: str, mask_path: str, tolerance: int = 0) -> bool:
    """
    mask==0 영역(바깥)이 원본과 동일한지 검사.
    tolerance=0이면 완전 동일 요구. (PNG 저장 권장)
    """
    room = Image.open(room_path).convert("RGB")
    out = Image.open(out_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")

    if room.size != out.size or room.size != mask.size:
        return False

    diff = ImageChops.difference(room, out)
    # 바깥(mask==0)만 검사해야 하므로 "mask 반전"을 이용해 바깥만 남긴다
    outside = ImageChops.invert(mask)
    diff_outside = Image.composite(diff, Image.new("RGB", room.size, (0, 0, 0)), outside)

    bbox = diff_outside.getbbox()
    if bbox is None:
        return True

    if tolerance <= 0:
        return False

    # tolerance > 0면 바깥 diff의 최대 채널값이 tolerance 이하인지 완화검사
    extrema = diff_outside.getextrema()  # ((min,max), (min,max), (min,max), (min,max))
    max_rgb = max(extrema[0][1], extrema[1][1], extrema[2][1])
    return max_rgb <= tolerance

def _force_outside_mask_original(room_path: str, out_path: str, mask_path: str) -> None:
    """
    Gemini 결과(out_path)에서 mask(흰색) 영역만 유지하고,
    mask 바깥은 원본(room_path) 픽셀로 강제로 덮어쓴다.
    """
    room = Image.open(room_path).convert("RGB")
    out = Image.open(out_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")

    if room.size != out.size or room.size != mask.size:
        # 사이즈가 다르면 강제 적용 불가
        return

    # mask==255인 영역은 out(생성), 나머지는 room(원본)
    soft = mask.filter(ImageFilter.GaussianBlur(6))  # 4~10 사이 추천
    final = Image.composite(out, room, soft)
    final.save(out_path)

# =========================
# /api/chat/analyze handler (CV + RECO + IMAGES)
# =========================
async def handle_chat_analyze(request: Request, body: AnalyzeBody) -> JSONResponse:
    sid, sid_is_new = _get_or_create_sid(request)
    key = sid

    data: Dict[str, Any] = {}

    ctx = get_user_ctx(key) or {}
    save_path = ctx.get("last_image_path")
    scene_id = ctx.get("scene_id")
    room_type = ctx.get("room_type")

    if not save_path or not os.path.exists(str(save_path)):
        return _json_with_sid(
            {"ok": False, "messages": [{"type": "text", "text": "업로드된 이미지가 없습니다."}]},
            sid, sid_is_new,
        )

    user_filters = body.filters if isinstance(body.filters, dict) else {}
    print("[ANALYZE] user_filters=", user_filters)

    set_user_ctx(key, {"filters": user_filters}, ttl_sec=60 * 60 * 6)

    # 1) CV 실행
    user_opts = {"scene_id": scene_id} if scene_id else {}
    try:
        out = _run_pipeline_compat(str(save_path), user_opts=user_opts)
    except Exception as e:
        return _json_with_sid(
            {"ok": False, "messages": [{"type": "text", "text": f"분석 중 오류: {e}"}]},
            sid, sid_is_new
        )

    data = out if isinstance(out, dict) else {}

    print("[ANALYZE] data.constraints=", data.get("constraints"))

    # CV 실행 직후 (out 받은 바로 다음)
    try:
        data["space"] = classify_space(data)
    except Exception as e:
        print("[WARN] classify_space failed:", e)
        data["space"] = {"type": "unknown", "reason": "classify_failed"}

    # ========================================================
    # 🚀 [기상청 ASOS 데이터 주입 및 보정]
    # ========================================================
    weather_res: Optional[Dict[str, Any]] = None

    try:
        weather_res = weather_client.fetch_growth_profile("108")
    except Exception as e:
        print("[WARN] weather_client failed:", e)

    if not isinstance(weather_res, dict):
        weather_res = {"ok": False, "reason": "weather_fetch_failed"}

    # --- 낮시간 테스트 (원하면 유지) ---
    # weather_res["solar_radiation"] = "2.5"
    # weather_res["ok"] = True
    # ---------------------------------

    data["solar"] = weather_res

    try:
        solar_summary = _solar_summary_from_asos(weather_res)
        if isinstance(solar_summary, dict) and solar_summary.get("ok"):
            data = _apply_solar_to_spots(data, solar_summary)
            print(f"☀️ 기상청 데이터 적용 성공: {weather_res.get('solar_radiation')} MJ/m2")
    except Exception as solar_err:
        print(f"☀️ 기상청 데이터 처리 중 최종 오류: {solar_err}")

    # =========================
    # 2) 추천 (보정된 data 전달)
    # =========================

    data = recommend_for_analysis(data, user_filters=user_filters)
    data["image_path"] = str(save_path)

    # ✅ 무조건 1장만 렌더 (3장 폐기)
    spots = data.get("spots") if isinstance(data.get("spots"), list) else []
    if not spots:
        data["spots"] = []
        spots = data["spots"]

    # ✅ 소형 여부 판단 (filters 기반)
    is_small = _is_small_from_filters(data, user_filters)

    chosen_idx = None

    # (1) 소형이면: 테이블/선반/책상 스팟 우선
    if is_small:
        for i, s in enumerate(spots):
            if not isinstance(s, dict):
                continue
            surf = (str(s.get("surface") or "")).lower()
            # 네 파이프라인 surface 값이 다양할 수 있어서 넓게 잡음
            if ("table" in surf) or ("desk" in surf) or ("shelf" in surf) or ("counter" in surf):
                chosen_idx = i
                break

    # (2) 못 찾았으면: 기존대로 floor 우선
    if chosen_idx is None:
        for i, s in enumerate(spots):
            if not isinstance(s, dict):
                continue
            surf = (str(s.get("surface") or "")).lower()
            if "floor" in surf:
                chosen_idx = i
                break

    # (3) 그래도 없으면: 0 + spots 비면 synthetic 생성
    if chosen_idx is None:
        chosen_idx = 0
        if len(spots) == 0:
            w, h = _get_img_wh(data)
            pt = [float(int(w * 0.55)), float(int(h * 0.82))]
            spots.append({
                "spot_index": 0,
                "surface": "floor",
                "synthetic": True,
                "score": 999,
                "pt": pt,
                "features": {"pt": list(pt), "center": list(pt)},
            })
            data["spots"] = spots

    # ✅ render_plan reason/spot_usage를 소형/대형에 맞게 내려준다 (이게 핵심)
    reason = "table_small" if is_small else "floor_large"
    data["render_plan"] = {"count": 1, "spot_indexes": [int(chosen_idx)], "reason": reason}

    try:
        spots[int(chosen_idx)]["spot_usage"] = "table_small" if is_small else "floor_large"
    except Exception:
        pass

    rp = data.get("render_plan")
    if isinstance(rp, dict):
        idxs = rp.get("spot_indexes") or []
        reason = (rp.get("reason") or "").lower()

        spots = data.get("spots") or []
        for i in idxs:
            try:
                i = int(i)
            except Exception:
                continue
            if 0 <= i < len(spots) and isinstance(spots[i], dict):
                if reason == "table_small":
                    spots[i]["spot_usage"] = "table_small"
                else:
                    spots[i]["spot_usage"] = "floor_large"

    # ✅ render_plan이 실제 합성 좌표(best_point) / best_spot에 반영되게 강제
    chosen_spot = _choose_spot_by_render_plan(data)
    if isinstance(chosen_spot, dict):
        data["best_spot"] = chosen_spot  # pick_spot 등 다른 플로우도 일관되게
        forced_best_point = _best_point_from_spot(chosen_spot)
    else:
        forced_best_point = None

    # ✅ 핵심: 합성에 쓰이는 좌표(best_point)까지 render_plan 기반으로 강제 고정
    if isinstance(forced_best_point, dict) and forced_best_point.get("pt"):
        data["best_point"] = {"pt": forced_best_point["pt"], "spot_index": forced_best_point.get("spot_index")}
        # 호환용 키들도 같이 박아두면 extract_best_point 구현이 뭐든 안 흔들림
        data["best_pt"] = forced_best_point["pt"]

    # 3) 결과 저장
    latest_json = os.path.join(RESULT_DIR, "result_latest.json")

    # ✅ Analyze 응답용: marker만 담는다
    spot_images: List[Dict[str, Any]] = []
    ts_ms = int(time.time() * 1000)

    try:
        with open(latest_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[WARN] write result_latest.json failed:", e)

    # 4) 결과 이미지 생성 (✅ Analyze 단계에서는 marker만 생성: 비용/로딩 절감)
    rp = data.get("render_plan") if isinstance(data, dict) else None
    render_idxs: List[int] = []

    spots = data.get("spots") if isinstance(data, dict) else []
    if not isinstance(spots, list):
        spots = []

    if isinstance(rp, dict):
        idxs = rp.get("spot_indexes")
        if isinstance(idxs, list):
            for x in idxs:
                try:
                    i = int(x)
                    if 0 <= i < len(spots):
                        render_idxs.append(i)
                except Exception:
                    pass

    if not render_idxs:
        render_idxs = [0]

    # 중복 제거
    render_idxs = list(dict.fromkeys(render_idxs))

    for ridx in render_idxs[:1]:
        try:
            if not (0 <= ridx < len(spots)):
                continue

            bp = _best_point_from_spot(spots[ridx])
            if not isinstance(bp, dict) or not bp.get("pt"):
                continue

            marker_path = os.path.join(RESULT_DIR, f"result_latest_marker_spot_{ridx}.png")

            # marker만 저장 (초록점만)
            composite_plant_on_original(
                original_image_path=str(save_path),
                best_point_obj=bp,
                out_path=marker_path,
                plant_png_path=None,  # 식물 없음
                # plant_width_ratio=0.22,
                anchor="bottom_center",
                add_green_dot=True,  # 초록점만
            )

            if os.path.exists(marker_path):
                u = cache_bust_url(request, to_results_url(marker_path), ts_ms)
                spot_images.append({
                    "name": f"marker_spot_{ridx}",
                    "url": u,
                    "image_url": u,
                    "spot_index": ridx,
                    "pt": bp.get("pt"),
                    "kind": "marker",
                })
        except Exception as e:
            print(f"[WARN][analyze][marker] ridx={ridx} err={e}")
            continue

    # 5) 응답
    return _json_with_sid(
        {
            "ok": True,
            "images": spot_images,
            "spot_images": spot_images,
            "cv_result": data,
        },
        sid,
        sid_is_new,
    )


# =========================
# Router-facing aliases
# =========================

async def chat_get(request: Request) -> JSONResponse:
    sid, sid_is_new = _get_or_create_sid(request)

    msgs = [
        {"type": "text", "text": "식물추천 AI입니다. 먼저 필터를 선택해주세요.", "payload": get_filters().get("payload")},
        # {"type": "text", "text": "필터를 선택해주세요.", "payload": get_filters().get("payload")},
        # {"type": "text", "text": "사진 업로드를 진행해주세요.", "payload": {"input": {"type": "image"}}},
    ]
    return _json_with_sid({"messages": msgs}, sid, sid_is_new)

async def chat_post(request: Request) -> JSONResponse:
    return await handle_chat_post(request)

async def chat_image(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    image: Optional[UploadFile] = File(None),
    meta: Optional[str] = Form(None),
    scene_id: Optional[str] = Form(None),
    room_type: Optional[str] = Form(None),
) -> JSONResponse:
    return await handle_chat_image(request, files=files, image=image, meta=meta, scene_id=scene_id, room_type=room_type,)

# =========================
# Spot pick / Filters / Scenes
# =========================

class PickSpotBody(BaseModel):
    spot_index: int
    plant_name: str
    regen: bool = False
    mode: Optional[str] = None

def get_filters():
    groups = [
        {"key": "experience", "label": "식물 경험", "options": ["초보자", "경험자"]},
        {"key": "pet", "label": "반려동물 여부", "options": ["예", "아니오"]},
    ]
    return {"groups": groups, "payload": {"type": "filters", "groups": groups}}

def _pick_plant_for_spot(top_plants: Any, spot_index: int) -> str:
    """
    - score 높은 식물 우선
    - 후보가 많아질수록 랜덤성 증가 (원본 로직 유지)
    """
    if not isinstance(top_plants, list) or len(top_plants) == 0:
        return "potted plant"

    ranked = sorted(
        [p for p in top_plants if isinstance(p, dict)],
        key=lambda x: x.get("score", 0),
        reverse=True,
    )

    if 0 <= spot_index < len(ranked):
        return ranked[spot_index].get("name") or "potted plant"

    weights = [max((p.get("score", 0.1) if isinstance(p, dict) else 0.1), 0.05) for p in ranked]
    chosen = random.choices(ranked, weights=weights, k=1)[0]
    return chosen.get("name") or "potted plant"

def _light_level_from_times(lp: Optional[Dict[str, Any]]) -> str:
    if not isinstance(lp, dict):
        return "medium"
    t = lp.get("times")
    if not isinstance(t, dict):
        return "medium"

    try:
        mx = max(float(t.get("morning") or 0), float(t.get("noon") or 0), float(t.get("evening") or 0))
    except Exception:
        return "medium"

    # 0~1 스케일 가정(네가 normalize해서 곱해두니까 대체로 이 범위에 옴)
    if mx >= 0.75:
        return "bright"
    if mx <= 0.35:
        return "dim"
    return "medium"

def _save_mask_overlay(room_path: str, mask_path: str, out_path: str, alpha: int = 120) -> str:
    room = Image.open(room_path).convert("RGBA")
    mask = Image.open(mask_path).convert("L")

    # 빨간색 오버레이 레이어 만들기
    overlay = Image.new("RGBA", room.size, (255, 0, 0, 0))
    # mask(흰영역)만 alpha 적용
    overlay.putalpha(mask.point(lambda p: int(alpha) if p > 0 else 0))

    blended = Image.alpha_composite(room, overlay).convert("RGB")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    blended.save(out_path)
    return out_path

async def chat_pick_spot(request: Request, body: PickSpotBody) -> JSONResponse:
    sid, sid_is_new = _get_or_create_sid(request)
    key = sid

    # ✅ 강제: 이미지 URL/ID는 무시하고 이름만 사용
    pid = ""
    plant_url = ""

    print("[RUNNING_FILE]", __file__)
    print("[RUNNING_FUNC] chat_pick_spot called")

    regen = bool(getattr(body, "regen", False))
    mode_raw = getattr(body, "mode", None)
    mode = (str(mode_raw).strip().lower() if mode_raw is not None else "")

    latest_json = os.path.join(RESULT_DIR, "result_latest.json")
    if not os.path.exists(latest_json):
        return _json_with_sid(
            {"messages": [{"type": "text", "text": "저장된 분석 결과가 없습니다. 먼저 analyze를 실행하세요."}]},
            sid, sid_is_new,
        )

    try:
        with open(latest_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return _json_with_sid(
            {"messages": [{"type": "text", "text": f"결과 파일을 읽지 못했습니다: {e}"}]},
            sid, sid_is_new,
        )

    spots = data.get("spots")
    if not isinstance(spots, list) or not spots:
        return _json_with_sid(
            {"messages": [{"type": "text", "text": "spots가 없습니다. analyze를 다시 실행하세요."}]},
            sid, sid_is_new,
        )

    # =========================
    # 1) render_plan 기반 렌더 대상 spot index 결정
    # =========================
    rp = data.get("render_plan") if isinstance(data, dict) else None
    render_reason = None
    render_idxs: List[int] = []

    if isinstance(rp, dict):
        render_reason = (rp.get("reason") or "").lower().strip()
        idxs = rp.get("spot_indexes")
        if isinstance(idxs, list):
            for x in idxs:
                try:
                    i = int(x)
                    if 0 <= i < len(spots):
                        render_idxs.append(i)
                except Exception:
                    pass

    # fallback
    if not render_idxs:
        try:
            render_idxs = [int(body.spot_index)]
        except Exception:
            render_idxs = [0]
        render_reason = "manual"

    # ✅ 무조건 1장만 렌더
    render_idxs = [render_idxs[0]] if render_idxs else [0]
    render_reason = render_reason or "single"

    # ✅ 안전: 범위 밖 index 제거 + 비면 0 fallback
    render_idxs = [i for i in render_idxs if isinstance(i, int) and 0 <= i < len(spots)]
    render_idxs = render_idxs[:1] if render_idxs else [0]

    # =========================
    # 2) 원본 이미지 경로
    # =========================
    ctx = get_user_ctx(key) or {}
    save_path = ctx.get("last_image_path")

    if not save_path or not os.path.exists(str(save_path)):
        save_path = data.get("image_path") or data.get("save_path")

    if not save_path or not os.path.exists(str(save_path)):
        return _json_with_sid(
            {"messages": [{"type": "text", "text": "원본 이미지 경로를 찾지 못했습니다."}]},
            sid, sid_is_new,
        )

    # =========================
    # 3) plant_name만 사용 (✅ 이미지 URL/다운로드/레퍼런스 금지)
    # =========================
    plant_name = (str(body.plant_name).strip() if getattr(body, "plant_name", None) else "")
    if not plant_name:
        return _json_with_sid(
            {"ok": False, "messages": [{"type": "text", "text": "plant_name이 비어있습니다."}]},
            sid, sid_is_new
        )

    # =========================
    # 4) 동일 식물로 spot별 렌더
    # =========================
    ts_ms = int(time.time() * 1000)
    images_payload: List[Dict[str, Any]] = []

    def add_ai_img(label: str, path: str, spot_index: int):
        if not path:
            print("[add_img][WARN] empty path", label, spot_index)
            return
        if not os.path.exists(path):
            print("[add_img][WARN] file not exists", path)
            return

        rel = to_results_url(path)
        if not rel:
            rel = f"/results/{os.path.basename(path)}"

        u = cache_bust_url(request, rel, ts_ms)

        images_payload.append({
            "name": "ai_edit",
            "kind": "ai_edit",
            "spot_index": int(spot_index),
            "label": label,

            # ✅ 핵심: 프론트가 읽는 필드
            "url": u,
            "image_url": u,

            # 디버그용(있어도 되고 없어도 됨)
            "out_path": path,
            "rel": rel,
        })

    for ridx in render_idxs:
        s = spots[ridx]
        forced = _best_point_from_spot(s)
        if not forced or not forced.get("pt"):
            continue

        lp = spots[ridx].get("light_profile") if isinstance(spots[ridx], dict) else None
        bias = ""
        if isinstance(lp, dict):
            bias = str(lp.get("bias") or "").strip().lower()

        level = _light_level_from_times(lp)
        light_sentence = f"Lighting: {level} (bias={bias})."

        best_point = {"pt": forced["pt"], "spot_index": forced.get("spot_index")}

        # pt 클램프
        w = int(data.get("image_w") or data.get("w") or 1248)
        h = int(data.get("image_h") or data.get("h") or 832)
        try:
            best_point["pt"][0] = float(best_point["pt"][0])
            best_point["pt"][1] = float(best_point["pt"][1])
        except Exception:
            pass
        best_point["pt"][0] = max(5.0, min(float(w) - 5.0, best_point["pt"][0]))
        best_point["pt"][1] = max(5.0, min(float(h) - 5.0, best_point["pt"][1]))

        mask_path = os.path.join(RESULT_DIR, f"mask_{sid}_spot_{ridx}.png")

        # ✅ 마스크 파일 생성 (없으면 Gemini가 mask not found로 터짐)
        _save_mask_for_spot(
            room_path=str(save_path),
            pt=best_point["pt"],
            out_path=mask_path,
            box_w=240,
            box_h=460,
            bottom_pad=10,
            feather=6,
        )

        # ✅ spot_usage 결정 (su 정의)
        su = ""
        if isinstance(spots[ridx], dict):
            su = (spots[ridx].get("spot_usage") or "").strip().lower()

        # render_plan reason이 table_small이면 우선 반영
        if (not su) and (render_reason == "table_small"):
            su = "table_small"

        # 그래도 없으면: user_filters로 소형이면 table_small, 아니면 floor_large
        if not su:
            try:
                # data["constraints"]나 ctx filters 등 네 구조에 맞춰 가져와도 됨
                # 여기서는 data/ctx에서 가능한 값만 대충 커버
                uf = (data.get("constraints") or {})
                size_pref = (uf.get("size_pref") or "").strip().lower()
                if size_pref in ("small", "소형", "미니"):
                    su = "table_small"
                else:
                    su = "floor_large"
            except Exception:
                su = "floor_large"

        blend_rule = (
            "- Match the room’s exposure and white balance.\n"
            "- Keep contrast low-to-medium (no HDR / no crisp look).\n"
            "- Slightly soften leaf detail; avoid over-sharp edges.\n"
            "- Slightly reduce saturation so it matches the room.\n"
            "- Add subtle image grain/noise to match the original photo.\n"
            "- If the floor is glossy, add a VERY subtle reflection under the pot.\n"
            "- The plant must look like it was photographed in the same scene.\n"
            "- Avoid studio lighting; use the same ambient indoor light as the room.\n"
            "- No halos or cutout edges; blend edges seamlessly with the background.\n"
        )

        if su == "table_small":
            placement_rule = (
                "- Place the plant ON TOP of a TABLE (tabletop) inside the mask.\n"
                "- The pot bottom MUST sit naturally on the table surface.\n"
                "- Do NOT place it on the floor.\n"
                "- Scale realistic: height approx 15–35cm.\n"
                "- Add a subtle contact shadow on the table.\n"
            )
        else:
            # default = floor_large
            placement_rule = (
                "- Place the pot on the FLOOR inside the mask.\n"
                "- The pot bottom MUST firmly touch the real floor.\n"
                "- Do NOT place it on tables, shelves, or furniture.\n"
                "- Scale realistic: height approx 40–80cm.\n"
                "- Add a soft contact shadow directly under the pot.\n"
                "- Shadow softness/direction must match the room.\n"
            )

        name_safe = "".join(c for c in (plant_name or "plant") if c.isalnum() or c in ("-", "_"))[:40]
        ai_out_path = os.path.join(RESULT_DIR, f"ai_inpaint_{sid}_spot_{ridx}_{name_safe}.png")

        prompt = f"""
        IMPORTANT: Do not change ANY pixels outside the mask (keep the original room exactly).
        Inside the mask, insert EXACTLY ONE realistic potted plant that matches the room’s lighting and perspective.

        Plant to generate:
        - Name: "{plant_name}"
        - Generate a plant that is commonly recognized by this name.
        - Do NOT use any reference images. Generate only from the name.

        Rules (must follow):
        - Generate EXACTLY ONE plant. No duplicates.
        - The plant must be entirely inside the white mask.
        {placement_rule}
        - Do NOT add any extra objects.
        - No square background, no pasted look.
        - Do NOT repaint the floor/table surface. Keep its original texture and color.
        - Only add the plant + a natural contact shadow. No white platform / no filled base.
        - Do NOT create any white/bright base, spotlight circle, rug, mat, platform, pedestal, or disc under the plant.
        - Do NOT brighten, repaint, smooth, or blur the floor/table surface. Keep the exact original texture.
        - The ONLY allowed new pixels are the plant itself and a small natural contact shadow directly under the pot.

        {blend_rule}
        {light_sentence}

        Return the edited full-resolution room image.
        """.strip()

        ok = False
        last_ret = None

        # ✅ 최대 2회 재시도(필요 최소)
        for attempt in range(2):
            ret = gemini_inpaint_with_reference(
                room_image_path=str(save_path),
                reference_image_path=None,
                mask_image_path=mask_path,
                prompt=prompt,
                out_path=ai_out_path,
            )

            last_ret = ret
            if (not isinstance(ret, dict)) or (not ret.get("ok")):
                continue
            if (not os.path.exists(ai_out_path)) or os.path.getsize(ai_out_path) == 0:
                continue

            ok = True
            break

        if not ok:
            return _json_with_sid(
                {
                    "ok": False,
                    "messages": [{"type": "text", "text": f"❌ Gemini inpaint 실패/검증실패 (spot={ridx})."}],
                    "debug": {
                        "spot": ridx,
                        "mask_path": mask_path,
                        "ai_out_path": ai_out_path,
                        "ret": last_ret,
                    },
                },
                sid, sid_is_new
            )

        # ✅ 바깥 픽셀 강제 원본 복원 (원판/바닥칠/번짐 방지)
        _force_outside_mask_original(str(save_path), ai_out_path, mask_path)

        # ✅ 성공한 경우에만 결과 반환
        add_ai_img("ai_inpaint", ai_out_path, ridx)

    if not images_payload:
        return _json_with_sid(
            {
                "ok": False,
                "messages": [
                    {
                        "type": "text",
                        "text": "❌ render 결과 이미지가 생성되지 않았습니다. (images_payload empty)"
                    }
                ],
                "debug": {
                    "render_reason": render_reason,
                    "render_idxs": render_idxs,
                    "save_path": str(save_path),
                },
            },
            sid,
            sid_is_new
        )

    # =========================
    # 5) 응답
    # =========================
    if render_reason == "table_small":
        text = "✅ 소형 식물 → 테이블 1개 스팟에 동일 식물로 생성했습니다."
    else:
        text = "✅ 동일 식물로 1개 스팟에 생성했습니다."

    if mode == "composite":
        text += " (composite only)"
    else:
        text += " (Gemini)"

    msgs: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    if images_payload:
        msgs.append({"type": "images", "text": "생성 결과", "images": images_payload})

    # ✅ 최종 안전장치: url/image_url 누락된 항목 제거 + 로그
    fixed = []
    for it in (images_payload or []):
        if not isinstance(it, dict):
            continue
        if not (it.get("url") or it.get("image_url")):
            print("[WARN] images_payload item missing url:", it)
            continue
        fixed.append(it)

    images_payload = fixed

    resp = {
        "ok": True,
        "images": images_payload,  # 프론트용 (바로 접근 가능)
        "spot_images": images_payload,
        "messages": msgs,  # 기존 챗 UI용 유지
        "cv_result": data,
        "render_reason": render_reason,
        "render_idxs": render_idxs,
    }
    return _json_with_sid(resp, sid, sid_is_new)


async def chat_render(request: Request, body: PickSpotBody) -> JSONResponse:
    return await chat_pick_spot(request, body)