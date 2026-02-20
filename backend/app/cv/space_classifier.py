from __future__ import annotations
from typing import Any, Dict, List, Optional

def _lower_list(xs: Any) -> List[str]:
    if not isinstance(xs, list):
        return []
    out: List[str] = []
    for x in xs:
        if isinstance(x, str):
            out.append(x.strip().lower())
    return out

def _scene_str(data: Dict[str, Any]) -> str:
    scene = data.get("scene")
    if isinstance(scene, str):
        return scene.lower()
    if isinstance(scene, dict):
        # 가능한 키들 흡수
        for k in ("id", "scene_id", "name", "label", "type"):
            v = scene.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip().lower()
    # 상위에 있을 수도
    for k in ("scene_id", "sceneId", "sceneType"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
    return ""

def classify_space(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    return:
      {
        "type": "욕실" | "거실" | "방",
        "confidence": 0~1,
        "signals": {...}
      }
    """
    # 1) 객체 리스트(있으면 가장 강력)
    # pipeline 결과 구조가 아직 확정이 아니라서 가능한 키들 다 훑음
    objects: List[str] = []
    for keypath in (
        ("det", "objects"),
        ("det", "labels"),
        ("objects",),
        ("detections",),
        ("yolo", "objects"),
        ("yolo", "labels"),
    ):
        cur: Any = result
        ok = True
        for k in keypath:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            if isinstance(cur, list):
                objects = _lower_list(cur)
                if objects:
                    break

    # detections가 dict list면 label/name 뽑기
    if not objects and isinstance(result.get("detections"), list):
        tmp = []
        for d in result["detections"]:
            if isinstance(d, dict):
                v = d.get("label") or d.get("name") or d.get("class")
                if isinstance(v, str):
                    tmp.append(v.lower())
        objects = tmp

    scene = _scene_str(result)

    # 2) 하드 룰 (확정)
    if "toilet" in objects:
        return {"type": "욕실", "confidence": 0.98, "signals": {"objects": objects, "scene": scene}}
    if "bed" in objects:
        return {"type": "방", "confidence": 0.98, "signals": {"objects": objects, "scene": scene}}
    if ("sofa" in objects) and ("tv" in objects):
        return {"type": "거실", "confidence": 0.93, "signals": {"objects": objects, "scene": scene}}

    # 3) 점수 룰
    score = {"욕실": 0.0, "거실": 0.0, "방": 0.0}

    bathroom = {"toilet": 5.0, "sink": 3.0, "shower": 3.0, "bathtub": 3.0, "bidet": 4.0}
    living   = {"sofa": 3.0, "tv": 3.0, "couch": 3.0, "coffee_table": 2.0, "table": 1.0}
    bedroom  = {"bed": 5.0, "pillow": 2.0, "wardrobe": 2.5, "desk": 2.0}

    for o in objects:
        if o in bathroom: score["욕실"] += bathroom[o]
        if o in living:   score["거실"] += living[o]
        if o in bedroom:  score["방"] += bedroom[o]

    # scene 문자열도 보조로
    if "bath" in scene or "toilet" in scene or "restroom" in scene:
        score["욕실"] += 2.0
    if "living" in scene or "lounge" in scene:
        score["거실"] += 2.0
    if "bed" in scene or "bedroom" in scene or "room" in scene:
        score["방"] += 1.5

    # 4) 결정 + confidence
    ranked = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
    top, top_s = ranked[0]
    second_s = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_s - second_s

    # 아무 단서도 없을 때 기본값(방) + 낮은 신뢰도
    if top_s <= 0.0:
        return {"type": "방", "confidence": 0.50, "signals": {"objects": objects, "scene": scene, "scores": score}}

    conf = max(0.55, min(0.95, 0.55 + 0.08 * margin))
    return {"type": top, "confidence": float(conf), "signals": {"objects": objects, "scene": scene, "scores": score}}