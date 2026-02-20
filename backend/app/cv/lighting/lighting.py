# daily light 계산

import numpy as np
import cv2

def rotate2d(vec, deg):
    rad = np.deg2rad(deg)
    c, s = np.cos(rad), np.sin(rad)
    x, y = float(vec[0]), float(vec[1])
    return np.array([c*x - s*y, s*x + c*y], dtype=np.float32)

def daily_light_area(pt, origins, base_dirs, img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    p = np.array([pt[0], pt[1]], dtype=np.float32)

    def one_time(dir_deg):
        best = 0.0
        for o, bd in zip(origins, base_dirs):
            dvec = rotate2d(bd, dir_deg)
            v = p - o
            dist = np.linalg.norm(v) + 1e-6
            v = v / dist
            align = max(0.0, float(np.dot(v, dvec)))
            decay = 1.0 / (1.0 + dist * 0.01)
            bright = float(gray[pt[1], pt[0]])
            s = 0.60 * align + 0.25 * decay + 0.15 * bright
            if s > best:
                best = s
        return best

    scores = {
        "morning": one_time(-25),
        "noon":    one_time(0),
        "evening": one_time(+25),
    }
    total = float(scores["morning"] + scores["noon"] + scores["evening"])
    return scores, total
