# door / path penalty

import numpy as np
import cv2

def find_door_point(core_mask):
    cnts, _ = cv2.findContours(core_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    pts = c.reshape(-1, 2)
    h, w = core_mask.shape

    best, best_score = None, -1e9
    for x, y in pts:
        edge = 0.0
        edge += (y / (h + 1e-6)) * 2.0
        edge += (1.0 - abs(x - w/2) / (w/2 + 1e-6)) * 0.2
        d_edge = min(x, w-1-x, y, h-1-y)
        edge += (1.0 - d_edge / (max(h, w) + 1e-6)) * 0.6
        if edge > best_score:
            best_score = edge
            best = (int(x), int(y))
    return best

def path_penalty_map(core_mask, start_pt, end_pt, width_px=28):
    h, w = core_mask.shape
    pen = np.zeros((h, w), np.float32)
    if start_pt is None or end_pt is None:
        return pen

    x0, y0 = start_pt
    x1, y1 = end_pt

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    vx, vy = (x1 - x0), (y1 - y0)
    vv = vx*vx + vy*vy + 1e-6

    t = ((xx - x0)*vx + (yy - y0)*vy) / vv
    t = np.clip(t, 0.0, 1.0)
    projx = x0 + t*vx
    projy = y0 + t*vy
    dist = np.sqrt((xx - projx)**2 + (yy - projy)**2)

    inside = (dist < width_px) & (core_mask > 0)
    pen[inside] = 1.0 - dist[inside] / (width_px + 1e-6)
    return pen