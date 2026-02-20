from __future__ import annotations

import os
import json
import time
import random
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from fastapi import Request, UploadFile
from app.config import BASE_DIR, RESULT_DIR, UPLOAD_DIR, ASSET_DIR

# 1. 외부 모듈 및 클라이언트
from app.cv.pipeline import run_pipeline
from app.reco.recommender import recommend_for_analysis
from app.solar.weather_client import AsosWeatherClient

# 2. 이미지 편집/합성 엔진 (경로 확인 필요)
from app.llm.image_edit import composite_plant_on_original
from app.llm.gemini.gemini_image_edit import gemini_edit_image

# 3. 채팅 관련 유틸 및 스토리지
from .chat_progress import progress
from .chat_storage import (
    get_user_ctx, set_user_ctx, get_user_state, set_user_state,
    db_save_reco, db_list_recos,
)
from .chat_utils import (
    abs_url, cache_bust_url, to_results_url, scene_to_label,
    now_kst_yyyymmdd_hhmm, get_lat_lot_from_meta, extract_best_xy
)


# --- ⚠️ [중요] 기존 코드에서 정의되지 않아 빨간 줄이 뜰 수 있는 더미/임시 함수들 ---
# 만약 실제 모듈이 있다면 상단에서 import 하시고, 없다면 아래처럼 정의가 되어있어야 합니다.

def load_rules(asset_dir: str):
    # 실제 규칙 로드 로직이 있다면 교체
    return {}


class ContextLoader:
    def __init__(self, **kwargs):
        pass


class LLMClient:
    def __init__(self, **kwargs):
        pass


# -------------------------------------------------------------------------

# 지식 그래프 및 LLM 인스턴스 (사용자님 코드 유지)
KG_RULES = load_rules(ASSET_DIR)
KG_LOADER = ContextLoader(mysql_client=None, redis_client=None, base_dir=BASE_DIR, user_ctx={})
KG_LLM = LLMClient()

# 경로 자동 생성
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# 파일 경로 상수
LATEST_JSON = os.path.join(RESULT_DIR, "result_latest.json")
LATEST_MARKER = os.path.join(RESULT_DIR, "result_latest_marker.png")
LATEST_COMPOSITE = os.path.join(RESULT_DIR, "result_latest_composite.png")
AI_EDIT_AUTO = os.path.join(RESULT_DIR, "result_latest_ai_edit_auto.png")
AI_EDIT_MANUAL = os.path.join(RESULT_DIR, "result_latest_ai_edit_manual.png")

# 기상청 클라이언트 초기화
weather_client = AsosWeatherClient()


# --- 헬퍼 함수들 ---

def load_latest_result() -> Dict[str, Any]:
    if not os.path.exists(LATEST_JSON):
        return {}
    try:
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except:
        return {}


def save_latest_result(data: Dict[str, Any]):
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def gen_auto_ai_edit(marker_path: str, best_xy: Optional[List[float]]):
    prompt = (
        "Add a realistic potted plant at the recommended spot on the floor. "
        "Match lighting and perspective naturally. Do not change the room layout."
    )
    if best_xy:
        prompt += f" The spot coordinates are {best_xy}."
    return gemini_edit_image(input_image_path=marker_path, prompt=prompt, out_path=AI_EDIT_AUTO)


def gen_manual_ai_edit(marker_path: str, prompt: str):
    return gemini_edit_image(input_image_path=marker_path, prompt=prompt, out_path=AI_EDIT_MANUAL)


def build_images_payload(request: Request, files: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    ts_ms = int(time.time() * 1000)
    out: List[Dict[str, Any]] = []
    for label, abs_path in files:
        if abs_path and os.path.exists(abs_path):
            out.append({"name": label, "url": cache_bust_url(request, to_results_url(abs_path), ts_ms)})
    return out


def pick_plant_for_spot(top_plants: Any, spot_index: int) -> str:
    if not isinstance(top_plants, list) or len(top_plants) == 0:
        return "potted plant"
    # score 기준 정렬
    ranked = sorted([p for p in top_plants if isinstance(p, dict)], key=lambda x: x.get("score", 0), reverse=True)

    if not ranked:
        return "potted plant"

    if spot_index < len(ranked):
        return ranked[spot_index].get("name") or "potted plant"

    weights = [max(p.get("score", 0.1), 0.05) for p in ranked]
    chosen = random.choices(ranked, weights=weights, k=1)[0]
    return chosen.get("name") or "potted plant"


# --- 메인 분석 핸들러 ---

async def handle_analysis_flow(request: Request, img_path: str, user_id: str):
    """
    분석 - 기상청 데이터 연동 - 식물 추천 흐름
    """
    # 1. 위치 정보 추출
    lat, lon = get_lat_lot_from_meta(img_path)

    # 2. 이미지 공간 분석 (CV)
    analysis = run_pipeline(img_path)

    # 3. 기상청 실측 광량 데이터 확보
    stn_id = "108"  # 서울 기본값 (매핑 함수 추가 가능)
    weather_res = weather_client.fetch_growth_profile(stn_id)

    if weather_res:
        analysis["solar"] = {
            "solar_radiation": weather_res.solar_radiation,
            "temperature": weather_res.temperature,
            "humidity": weather_res.humidity,
            "observed_at": weather_res.raw.get("tm"),
            "provider": weather_res.provider
        }
    else:
        analysis["solar"] = None

    # 4. 식물 추천 엔진 가동
    user_ctx = get_user_ctx(user_id)
    user_filters = user_ctx.get("filters", {})

    # recommender.py의 로직을 통해 spots 점수 계산
    analysis = recommend_for_analysis(analysis, user_filters)

    # 5. 결과 저장
    save_latest_result(analysis)

    return analysis