from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from app.cv.pipeline import list_71765_scenes
from app.cv.scene_room_infer import load_scene_json, infer_room_type_from_scene_json

# 네 실제 경로로 고정
# DEFAULT_SCENE_ROOT = Path(r"C:\Users\201\Desktop\71765_json\71765_json")
DEFAULT_SCENE_ROOT = Path(r"C:\Users\나\Desktop\71765_json\71765_json")

def build_room_groups(scene_root: Path = DEFAULT_SCENE_ROOT) -> Dict[str, List[str]]:
    """
    room_type(거실/침실/주방/욕실/기타) -> [scene_id...]
    """
    raw = list_71765_scenes()
    scene_ids: List[str] = []

    if isinstance(raw, list):
        scene_ids = [str(x) for x in raw]
    elif isinstance(raw, dict):
        scene_ids = [str(k) for k in raw.keys()]

    groups: Dict[str, List[str]] = {"거실": [], "침실": [], "주방": [], "욕실": [], "기타": []}

    for sid in scene_ids:
        sj = load_scene_json(scene_root, sid)
        if not sj:
            continue
        room = infer_room_type_from_scene_json(sj)
        if room not in groups:
            room = "기타"
        groups[room].append(sid)

    return groups


def pick_scene_for_room(groups: Dict[str, List[str]], room_type: str, seed: Optional[str] = None) -> Optional[str]:
    """
    room_type 하나를 받으면 그 그룹에서 scene_id 하나를 골라준다.
    - seed를 주면 유저 세션마다 같은 선택을 유지할 수 있음
    """
    room_type = (room_type or "").strip()
    candidates = groups.get(room_type) or []
    if not candidates:
        return None

    if seed:
        r = random.Random(seed)
        return r.choice(candidates)
    return random.choice(candidates)
