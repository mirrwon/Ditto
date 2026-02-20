from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class SolarProfile:
    provider: str
    fetched_at: float

    lat: float
    lon: float
    tz: str  # "Asia/Seoul"
    date: str  # "YYYY-MM-DD"

    # 핵심: 시간대별 “유효 일사량” (정규화된 값)
    # 단위는 0~1 normalize 로 통일 추천 (제품형 확장에 유리)
    ghi_norm: Dict[str, float]  # {"morning":0.7, "noon":0.9, "evening":0.5}

    raw: Dict[str, Any]  # 원본 응답(디버깅/증거용)
