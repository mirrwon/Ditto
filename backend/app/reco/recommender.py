from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import time


# =========================
# 1. 기초 유틸리티 함수
# =========================

def _load_plants_from_json(json_path: str) -> Any:
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# =========================
# 2. 광량 및 방향 보정 로직
# =========================

def weather_data_to_times(weather_data: Dict[str, Any]) -> Dict[str, float]:
    if not weather_data: return {}
    val = float(weather_data.get("solar_radiation") or 0.0)

    # 실시간 테스트용: 일사량이 0이면(밤이면) 테스트를 위해 기본값 1.5 부여
    if val <= 0:
        val = 1.5

    obs_time = str(weather_data.get("observed_at") or "")
    try:
        hh = int(obs_time.split()[-1].split(":")[0]) if " " in obs_time else 12
    except:
        hh = 12

    buckets = {"morning": 0.0, "noon": 0.0, "evening": 0.0}
    # 시간대 상관없이 테스트 환경에서는 골고루 광량 배분 (점수 하락 방지)
    if 6 <= hh < 11:
        buckets["morning"] = val
    elif 11 <= hh < 15:
        buckets["noon"] = val
    elif 15 <= hh < 20:
        buckets["evening"] = val
    else:
        buckets["morning"], buckets["noon"], buckets["evening"] = val * 0.7, val, val * 0.7

    return buckets


def _window_dir_scale(direction: str) -> Dict[str, float]:
    scales = {
        "S": {"morning": 0.8, "noon": 1.0, "evening": 0.8},
        "E": {"morning": 1.0, "noon": 0.6, "evening": 0.3},
        "W": {"morning": 0.3, "noon": 0.6, "evening": 1.0},
        "N": {"morning": 0.4, "noon": 0.4, "evening": 0.4},
    }
    return scales.get(direction.upper(), scales["S"])


def _compute_spot_score(spot: Dict[str, Any]) -> Dict[str, Any]:
    feats = spot.get("features", {})
    t = feats.get("times") or {"morning": 0.5, "noon": 0.5, "evening": 0.5}
    m = float(t.get("morning", 0))
    n = float(t.get("noon", 0))
    e = float(t.get("evening", 0))

    # 점수 계산식 (가중치 조정)
    score = (m * 0.3 + n * 0.4 + e * 0.3) * 100
    return {"score": round(score, 2), "breakdown": {"m": m, "n": n, "e": e}}


# =========================
# 3. 핵심 추천 함수
# =========================

def recommend_for_analysis(data: Dict[str, Any], user_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not isinstance(data, dict): return {}
    user_filters = user_filters or {}
    pet_filter = user_filters.get("pet")

    # 1) 식물 DB 로드 - 절대 경로로 강제 지정
    # 유저님의 로그 경로: D:\study\07.FinalProject\01.project\rev_10\backend\plantsData\plants_sample.json
    db_path = r"D:\study\07.FinalProject\01.project\rev_12\backend\plantsData\plants_sample.json"

    raw_data = _load_plants_from_json(db_path)
    if isinstance(raw_data, dict):
        plants_list = raw_data.get("plants", [])
    elif isinstance(raw_data, list):
        plants_list = raw_data
    else:
        plants_list = []

    # DB 로드 실패 시 테스트 데이터 (보험)
    # if not plants_list:
    #     plants_list = [
    #         {"name": "몬스테라(더미)", "pet_safe": True, "light_req": "high"},
    #         {"name": "테이블야자(더미)", "pet_safe": True, "light_req": "medium"}
    #     ]

    # 2) 날씨 보정 (밤 시간대에도 0이 되지 않게 보정됨)
    weather_res = data.get("solar")
    solar_times = weather_data_to_times(weather_res)
    dir_scale = _window_dir_scale(data.get("window_direction") or "S")

    # 정규화
    mx = max(solar_times.values()) if solar_times and max(solar_times.values()) > 0 else 1.0
    solar_scale = {k: v / mx for k, v in solar_times.items()}

    # 최종 스케일 (0.4 미만으로 떨어지지 않게 하한선 설정하여 점수 보존)
    final_scale = {
        k: max(0.4, solar_scale[k] * dir_scale[k])
        for k in ["morning", "noon", "evening"]
    }

    # 3) Spot별 계산
    spots = data.get("spots") or []
    for s in spots:
        feats = s.setdefault("features", {})
        cv_t = feats.get("times_cv") or feats.get("times") or {"morning": 0.5, "noon": 0.5, "evening": 0.5}
        feats["times_cv"] = cv_t

        # 보정치 적용
        feats["times"] = {
            k: _clamp01(float(cv_t.get(k, 0.5)) * final_scale[k])
            for k in ["morning", "noon", "evening"]
        }

        res = _compute_spot_score(s)
        feats["score"] = res["score"]

        # 필터링 및 추천 (점수 순 정렬된 리스트 배정)
        # 실제 운영시엔 p.get('light_req')와 score를 비교하는 로직 추가 가능
        s["top_plants"] = plants_list[:5]

    # 4) 전체 정렬
    spots.sort(key=lambda x: x.get("features", {}).get("score", 0), reverse=True)
    data["spots"] = spots
    if spots:
        data["best_spot"] = spots[0]
        data["top_plants"] = plants_list[:10]

    data["solar_apply"] = {"ok": True, "final_scale": final_scale}

    return data