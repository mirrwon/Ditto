from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

def load_scene_json(scene_root: Path, scene_id: str) -> Optional[Dict[str, Any]]:
    # scene_id 폴더 안에 json이 있다고 가정: {scene_root}/{scene_id}/{scene_id}.json
    # 네 실제 구조에 맞게 file path만 여기서 고정하면 됨
    p1 = scene_root / scene_id / f"{scene_id}.json"
    p2 = scene_root / f"{scene_id}.json"  # 혹시 평면 구조면

    path = p1 if p1.exists() else (p2 if p2.exists() else None)
    if path is None:
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def infer_room_type_from_scene_json(scene_json: Dict[str, Any]) -> str:
    """
    scene_json 내부의 metadata를 보고 '거실/침실/주방/욕실/기타'로 정규화해서 리턴.
    - 네 데이터셋 metadata 키가 다르면 아래 meta 접근만 바꿔.
    """
    meta = scene_json.get("metadata", {}) if isinstance(scene_json, dict) else {}
    if not isinstance(meta, dict):
        meta = {}

    # 데이터에 따라 space_subclass / space_detail / room_type 같은 키가 있을 수 있음
    s1 = str(meta.get("space_subclass") or "").strip()
    s2 = str(meta.get("space_detail") or "").strip()
    raw = f"{s1} {s2}".strip()

    # 키워드 매핑 (여기만 손보면 됨)
    if any(k in raw for k in ["욕실", "화장실", "bath", "toilet"]):
        return "욕실"
    if any(k in raw for k in ["주방", "부엌", "kitchen"]):
        return "주방"
    if any(k in raw for k in ["거실", "living"]):
        return "거실"
    if any(k in raw for k in ["침실", "방", "bed", "bedroom"]):
        return "침실"

    return "기타"
