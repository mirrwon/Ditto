# v7 / v8 차광

import numpy as np

def occ_v7_stability(p0, p1, stab, core_mask, ray_samples=22, thr=0.55):
    h, w = stab.shape
    x0, y0 = p0
    x1, y1 = p1
    bad = 0
    valid = 0
    for i in range(1, ray_samples+1):
        t = i / (ray_samples + 1)
        x = int(x0 + (x1 - x0) * t)
        y = int(y0 + (y1 - y0) * t)
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        if core_mask[y, x] == 0:
            continue
        valid += 1
        if float(stab[y, x]) < thr:
            bad += 1
    if valid == 0:
        return 0.0
    return float(np.clip(bad / valid, 0, 1))

def occ_v8_depth(p0, p1, depth, core_mask, ray_samples=22, depth_thr=0.06):
    h, w = depth.shape
    x0, y0 = p0
    x1, y1 = p1
    prev = None
    hits = 0
    valid = 0
    for i in range(1, ray_samples+1):
        t = i / (ray_samples + 1)
        x = int(x0 + (x1 - x0) * t)
        y = int(y0 + (y1 - y0) * t)
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        if core_mask[y, x] == 0:
            continue
        d = float(depth[y, x])
        if prev is not None and (d - prev) > depth_thr:
            hits += 1
        prev = d
        valid += 1
    if valid == 0:
        return 0.0
    return min(1.0, hits / valid)
