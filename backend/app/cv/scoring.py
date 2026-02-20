# 점수 계산

def cluster_and_pick(items, cluster_dist=55, max_total=6):
    clusters = []
    for it in items:
        score, pt, meta = it
        x, y = pt
        placed = False
        for c in clusters:
            cx, cy = c["center"]
            if (x-cx)**2 + (y-cy)**2 < cluster_dist**2:
                c["items"].append(it)
                n = len(c["items"])
                c["center"] = ((cx*(n-1)+x)/n, (cy*(n-1)+y)/n)
                placed = True
                break
        if not placed:
            clusters.append({"center": (x, y), "items": [it]})

    clusters.sort(key=lambda c: max(v[0] for v in c["items"]), reverse=True)

    picked = []
    for c in clusters:
        c["items"].sort(key=lambda v: v[0], reverse=True)
        picked.append(c["items"][0])
        if len(picked) >= max_total:
            break

    picked.sort(key=lambda v: v[0], reverse=True)
    return picked
