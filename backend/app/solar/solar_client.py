from __future__ import annotations

import os
import time
import json
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import unquote

import requests
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SolarProfile:
    """
    식물 생장용 공용 스키마
    - solar_radiation: 실측 일사량 (MJ/m2)
    - temperature: 실측 기온 (℃)
    - humidity: 실측 습도 (%)
    - provider: 데이터 출처 (기상청 ASOS)
    """
    provider: str
    fetched_at: float
    stn_id: str
    stn_nm: str
    solar_radiation: float
    temperature: float
    humidity: float
    raw: Dict[str, Any]


class AsosWeatherClient:
    """
    기상청 ASOS(종관기상관측) API 기반 클라이언트.

    핵심 설계:
    - .env로부터 WEATHER_API_SERVICE_KEY 주입
    - 지상 실측 데이터(일사량, 온도, 습도) 통합 추출
    - 동일 지점/시간 반복 호출 방지 캐시 시스템 탑재
    """

    def __init__(
            self,
            base_url: Optional[str] = None,
            service_key: Optional[str] = None,
            timeout_sec: int = 10,
            cache_ttl_sec: int = 60 * 30,  # 30분 캐시
    ) -> None:
        # 보내주신 명세서의 기본 URL
        self.base_url = (base_url or os.getenv("WEATHER_API_URL",
                                               "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList")).strip()
        # 보안을 위해 unquote 처리
        self.service_key = unquote((service_key or os.getenv("WEATHER_API_SERVICE_KEY", "")).strip())
        self.timeout_sec = int(timeout_sec)
        self.cache_ttl_sec = int(cache_ttl_sec)

        self._cache: Dict[str, Tuple[float, SolarProfile]] = {}

    def is_configured(self) -> bool:
        return bool(self.base_url) and bool(self.service_key)

    def fetch_growth_profile(self, stn_id: str = "108") -> Optional[SolarProfile]:
        """
        - stn_id: 기상청 지점 번호 (서울: 108)
        """
        if not self.is_configured():
            print("[ASOS] 설정 오류: URL 또는 키가 없습니다.")
            return None

        # 1. 캐시 확인
        cache_key = self._make_cache_key(stn_id)
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        # 2. 시간 설정 (실측 데이터 동기화를 위해 1시간 전 데이터 조회)
        target_dt = datetime.now() - timedelta(hours=1)
        date_str = target_dt.strftime("%Y%m%d")
        hour_str = target_dt.strftime("%H")

        params = {
            "serviceKey": self.service_key,
            "pageNo": "1",
            "numOfRows": "10",
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "HR",
            "stnIds": stn_id,
            "startDt": date_str,
            "startHh": hour_str,
            "endDt": date_str,
            "endHh": hour_str
        }

        try:
            r = requests.get(self.base_url, params=params, timeout=self.timeout_sec)
            r.raise_for_status()
            res_data = r.json()

            items = res_data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if not items:
                print(f"[ASOS] {date_str} {hour_str}시 실측 데이터가 아직 없습니다.")
                return None

            data = items[0]

            # 3. 데이터 추출 및 정제 (MJ/m2 단위)
            prof = SolarProfile(
                provider="KMA_ASOS",
                fetched_at=time.time(),
                stn_id=stn_id,
                stn_nm=data.get("stnNm", "알 수 없음"),
                solar_radiation=self._safe_float(data.get("icsr")),  # 일사량
                temperature=self._safe_float(data.get("ta")),  # 기온
                humidity=self._safe_float(data.get("hm")),  # 습도
                raw=data,
            )

            self._set_cache(cache_key, prof)
            return prof

        except Exception as e:
            print(f"[ASOS] 데이터 획득 실패: {e}")
            return None

    def _safe_float(self, val: Any) -> float:
        try:
            if val is None or str(val).strip() == "": return 0.0
            return float(val)
        except:
            return 0.0

    # ----------------
    # Cache Logic (기존 유지)
    # ----------------
    def _make_cache_key(self, stn_id: str) -> str:
        # 시간 단위로 데이터가 바뀌므로 시간까지 키에 포함
        hour_key = datetime.now().strftime("%Y%m%d%H")
        s = f"{stn_id}_{hour_key}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _get_cache(self, key: str) -> Optional[SolarProfile]:
        v = self._cache.get(key)
        if not v: return None
        ts, prof = v
        if (time.time() - ts) > self.cache_ttl_sec:
            self._cache.pop(key, None)
            return None
        return prof

    def _set_cache(self, key: str, prof: SolarProfile) -> None:
        self._cache[key] = (time.time(), prof)