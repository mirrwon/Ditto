from pydantic import BaseModel


class PickSpotBody(BaseModel):
    spot_index: int
    regen: bool = False  # 기본은 캐시 모드