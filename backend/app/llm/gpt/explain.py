# XAI / FAIL

def explain(meta):
    tags = []
    L = meta["light_eff"]
    occ = meta["occ"]
    path = meta["path"]
    wall = meta["wall"]
    stab = meta["stab"]
    t = meta["times"]

    if L > 1.4: tags.append("채광 좋음")
    elif L > 1.0: tags.append("채광 무난")
    else: tags.append("채광 약함")

    if t["morning"] >= max(t["noon"], t["evening"]): tags.append("오전 유리")
    elif t["evening"] >= max(t["noon"], t["morning"]): tags.append("오후 유리")
    else: tags.append("정오 유리")

    if occ < 0.15: tags.append("차광 적음")
    elif occ > 0.40: tags.append("차광 큼")

    if path < 0.15: tags.append("동선 안전")
    elif path > 0.45: tags.append("동선 근접")

    if wall > 0.60: tags.append("벽거리 여유")
    elif wall < 0.25: tags.append("벽 근접")

    if stab > 0.70: tags.append("바닥 안정")
    elif stab < 0.35: tags.append("경계/장애물 가능")

    return " / ".join(tags[:3])

def failure_labels(meta):
    labels = []
    if meta["path"] > 0.50:
        labels.append("too_close_to_path")
    if meta["wall"] < 0.20:
        labels.append("too_close_to_wall")
    if meta["stab"] < 0.30:
        labels.append("low_stability")
    if meta["occ"] > 0.45:
        labels.append("high_occlusion")
    if meta["light_eff"] > 2.0:
        labels.append("overbright_possible")
    return labels
