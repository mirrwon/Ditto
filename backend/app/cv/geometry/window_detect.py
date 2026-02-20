# 창문감지 + 광원

import numpy as np
import cv2

def detect_window_candidate(image_bgr, floor_mask, prefer="right", debug=False):
    h, w = floor_mask.shape
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    ys, xs = np.where(floor_mask > 0)
    if len(xs) < 200:
        return None

    y_floor_top = int(np.quantile(ys, 0.05))
    y1 = int(np.clip(y_floor_top + h * 0.60, 80, h))
    wall = gray[:y1, :]

    wall_blur = cv2.GaussianBlur(wall, (5, 5), 0)
    thr = int(np.clip(np.percentile(wall_blur, 80), 135, 235))
    bw = (wall_blur >= thr).astype(np.uint8) * 255

    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8), iterations=2)

    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None

    best, best_score = None, -1e9
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)
        area = ww * hh
        if area < (w * y1) * 0.008:
            continue

        peri = cv2.arcLength(c, True)
        compact = area / (peri * peri + 1e-6)
        if compact < 0.002:
            continue

        patch = wall[y:y+hh, x:x+ww]
        mean_b = float(np.mean(patch)) / 255.0

        cx = x + ww * 0.5
        edge_bias = (cx / (w + 1e-6)) if prefer == "right" else (1.0 - cx / (w + 1e-6))

        aspect = max(ww / (hh + 1e-6), hh / (ww + 1e-6))
        aspect_bonus = np.clip((aspect - 1.2) / 2.5, 0, 1)
        top_bonus = 1.0 - (y / (y1 + 1e-6))

        score = (
            (area / (w * y1 + 1e-6)) * 2.4 +
            mean_b * 1.4 +
            edge_bias * 0.9 +
            aspect_bonus * 0.6 +
            top_bonus * 0.3
        )

        if score > best_score:
            best_score = score
            best = (x, y, ww, hh)

    if debug and best is not None:
        print("[WIN] bbox:", best, "thr:", thr, "score:", best_score)

    return best

def window_segment_points(win_bbox, n=9):
    x, y, w, h = win_bbox
    y_seg = y + h * 0.70
    xs = np.linspace(x + w * 0.15, x + w * 0.85, int(n))
    return [np.array([float(xx), float(y_seg)], dtype=np.float32) for xx in xs]

def base_dir(origin, floor_c):
    v = floor_c - origin
    return (v / (np.linalg.norm(v) + 1e-6)).astype(np.float32)
