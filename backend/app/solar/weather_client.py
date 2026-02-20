import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class AsosWeatherClient:
    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_SERVICE_KEY")
        self.base_url = os.getenv("WEATHER_API_URL")

    def fetch_growth_profile(self, station_id: str = "108") -> Dict[str, Any]:
        """
        기상청 ASOS API를 호출하여 실시간 일사량 데이터를 가져옵니다.
        'chat_handlers.py'에서 이 함수명을 호출하므로 이름을 일치시켰습니다.
        """
        if not self.api_key or not self.base_url:
            print("[AsosWeatherClient] ERROR: .env에 WEATHER_API_SERVICE_KEY 또는 WEATHER_API_URL이 설정되지 않았습니다.")
            return self._get_default_data(station_id)

        now = datetime.now()
        # 현재 시간 기준 1시간 전 데이터 요청
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H")

        params = {
            "serviceKey": self.api_key,
            "numOfRows": "1",
            "pageNo": "1",
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "HR",
            "startDt": date_str,
            "startHh": time_str,
            "endDt": date_str,
            "endHh": time_str,
            "stnIds": station_id
        }

        try:
            # API 호출
            response = requests.get(self.base_url, params=params, timeout=5)

            if response.status_code != 200:
                print(f"[AsosWeatherClient] API 연결 실패: HTTP {response.status_code}")
                return self._get_default_data(station_id)

            res_data = response.json()
            items = res_data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

            if items:
                item = items[0]
                # 일사량(icsr) 실측값 추출
                solar_val = item.get("icsr")
                return {
                    "solar_radiation": solar_val if solar_val else "0.0",
                    "temperature": item.get("ta", "15.0"),
                    "observed_at": f"{item.get('tm', now.strftime('%Y-%m-%d %H:00'))}",
                    "stn_id": station_id,
                    "ok": True if solar_val else False
                }
            else:
                print("[AsosWeatherClient] 관측 데이터 항목(item)이 비어 있습니다.")
        except Exception as e:
            print(f"[AsosWeatherClient] Exception occurred: {e}")

        return self._get_default_data(station_id)

    def _get_default_data(self, station_id: str) -> Dict[str, Any]:
        """API 호출 실패 시 시스템 중단을 막기 위한 폴백(Fallback) 데이터"""
        return {
            "solar_radiation": "0.0",
            "temperature": "15.0",
            "observed_at": datetime.now().strftime("%Y-%m-%d %H:00"),
            "stn_id": station_id,
            "ok": False,
            "note": "fallback_default"
        }