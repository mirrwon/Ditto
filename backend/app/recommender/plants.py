# 식물추천

from typing import List, Dict

PLANTS = [
    {"name":"산세베리아", "min":0.70, "max":1.20, "pet_safe":True,  "care":1, "tags":["초보","저광량"]},
    {"name":"스투키",     "min":0.60, "max":1.10, "pet_safe":True,  "care":1, "tags":["초보","저광량"]},
    {"name":"아레카야자", "min":1.10, "max":1.70, "pet_safe":True,  "care":2, "tags":["공기정화"]},
    {"name":"올리브나무", "min":1.40, "max":2.20, "pet_safe":True,  "care":3, "tags":["고광량","관리어려움"]},
    {"name":"몬스테라",   "min":1.00, "max":1.60, "pet_safe":False, "care":2, "tags":["주의(반려동물)"]},
]

def plant_light_score(light_eff, p):
    mn, mx = float(p["min"]), float(p["max"])
    if mn <= light_eff <= mx:
        return 1.0
    d = (mn - light_eff) if light_eff < mn else (light_eff - mx)
    return float(1.0 / (1.0 + d * 2.0))

def plant_care_penalty(is_beginner, plant_care):
    try:
        c = int(plant_care)
    except:
        c = 2
    if is_beginner:
        return float({1: 0.0, 2: 0.15, 3: 0.35}.get(c, 0.2))
    else:
        return 0.0

def recommend_plants(light_eff: float, user_opts: Dict, topk: int = 5) -> List[Dict]:
    rec = []
    pet = bool((user_opts or {}).get("pet", False))
    is_beginner = bool((user_opts or {}).get("is_beginner", True))

    for p in PLANTS:
        if pet and (p.get("pet_safe", True) is False):
            continue

        ls = plant_light_score(float(light_eff), p)

        plant_care = p.get("care", 2) or 2
        pen = float(plant_care_penalty(is_beginner, plant_care))
        care_score = max(0.0, 1.0 - pen)

        final = 0.70 * ls + 0.30 * care_score
        in_range = (float(p["min"]) <= float(light_eff) <= float(p["max"]))

        reason = []
        reason.append("광량 적합" if in_range else "광량 근접")
        if is_beginner:
            reason.append("초보 OK" if int(plant_care) <= 2 else "초보에 어려움")
        else:
            reason.append("관리 여유")

        rec.append({
            "name": p["name"],
            "score": float(final),
            "in_range": bool(in_range),
            "light_score": float(ls),
            "care_score": float(care_score),
            "care": int(plant_care),
            "pet_safe": bool(p.get("pet_safe", True)),
            "reason": " / ".join(reason),
            "tags": p.get("tags", []),
            "min": float(p["min"]),
            "max": float(p["max"]),
        })

    rec.sort(key=lambda x: x["score"], reverse=True)
    return rec[:topk]
