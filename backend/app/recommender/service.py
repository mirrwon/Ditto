from __future__ import annotations
from typing import Any, Dict, List, Optional
import os

from app.solar.weather_client import AsosWeatherClient
from app.reco.recommender import recommend_for_analysis


# ✅ 서비스 클래스화 (상태 관리 및 확장성 고려)
class RecommendationService:
    def __init__(self):
        # .env에서 키를 로드하는 클라이언트 초기화
        self.weather_client = AsosWeatherClient()

    def process_full_analysis(
            self,
            analysis_data: Dict[str, Any],
            user_filters: Optional[Dict[str, Any]] = None,
            lat: float = 37.5665,
            lon: float = 126.9780
    ) -> Dict[str, Any]:
        """
        1. 기상청 실측 데이터 획득 (ASOS)
        2. 분석 데이터(CV 결과)와 기상 데이터 결합
        3. Recommender를 통한 점수 계산 및 식물 추천
        """

        # --- 1. 기상청 실측 데이터 가져오기 ---
        # TODO: 위경도(lat, lon)를 stn_id로 변환하는 로직 추가 필요. 일단 서울(108) 고정.
        stn_id = self._get_stn_id_from_coords(lat, lon)
        weather_profile = self.weather_client.fetch_growth_profile(stn_id)

        # --- 2. 분석 데이터에 기상 정보 주입 ---
        if weather_profile:
            # recommender.py가 기대하는 구조로 데이터 변환
            analysis_data["solar"] = {
                "solar_radiation": weather_profile.solar_radiation,
                "temperature": weather_profile.temperature,
                "humidity": weather_profile.humidity,
                "observed_at": weather_profile.raw.get("tm"),
                "stn_nm": weather_profile.stn_nm,
                "provider": weather_profile.provider
            }
        else:
            analysis_data["solar"] = None

        # --- 3. 최종 추천 및 스코어링 진행 ---
        # 여기서 recommender.py 내의 모든 보정(창방향, 시간대별 가중치)이 일어납니다.
        final_result = recommend_for_analysis(analysis_data, user_filters)

        return final_result

    def _get_stn_id_from_coords(self, lat: float, lon: float) -> str:
        """
        위경도 좌표를 기반으로 가장 가까운 기상청 관측소 ID 반환
        (우선은 서울 108번 고정, 추후 매핑 테이블 적용)
        """
        return "108"


# ✅ 기존 함수형 인터페이스 유지 (하위 호환성)
def run_recommendation_service(analysis, filters, lat=None, lon=None):
    svc = RecommendationService()
    return svc.process_full_analysis(analysis, filters, lat or 37.56, lon or 126.97)