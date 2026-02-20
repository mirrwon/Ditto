import cv2
import numpy as np
from typing import Any

from app.cv.cv_config import DEPTH_OCC_THRESHOLD

# =========================
# UTILS (RESTORED)
# =========================

def floor_core(mask01: np.ndarray, k: int = 19) -> np.ndarray:
    """바닥 마스크 중심부(안전 영역)만 남기기용 erosion"""
    ker = np.ones((k, k), np.uint8)
    return cv2.erode(mask01.astype(np.uint8), ker, iterations=1)


def candidates_from_mask(mask01: np.ndarray, step: int = 18) -> list[tuple[int, int]]:
    """mask 위에서 일정 간격으로 후보 점 샘플링"""
    ys, xs = np.where(mask01 > 0)
    if xs.size == 0:
        return []
    y_min, y_max = int(ys.min()), int(ys.max())
    x_min, x_max = int(xs.min()), int(xs.max())

    pts = []
    for y in range(y_min, y_max + 1, step):
        for x in range(x_min, x_max + 1, step):
            if mask01[y, x] > 0:
                pts.append((x, y))
    return pts


def distance_to_boundary(mask01: np.ndarray) -> np.ndarray:
    """
    바닥 마스크 내부에서 '경계까지 거리'를 0~1로 정규화한 값.
    값이 클수록 벽/경계에서 멀다.
    """
    m = (mask01 > 0).astype(np.uint8)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    if dist.max() <= 1e-6:
        return np.zeros_like(dist, dtype=np.float32)
    dist = dist / (dist.max() + 1e-6)
    return dist.astype(np.float32)


def depth_stability(depth: np.ndarray, k: int = 7) -> np.ndarray:
    """
    depth의 지역 변화량 기반 안정성(0~1).
    변화량이 작을수록 안정(=1에 가까움)
    """
    d = depth.astype(np.float32)
    blur = cv2.GaussianBlur(d, (0, 0), 2.0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx * gx + gy * gy)

    # grad가 작으면 안정 -> 1 - normalize
    gmax = float(np.percentile(grad, 95)) if grad.size else 1.0
    gmax = max(gmax, 1e-6)
    stab = 1.0 - np.clip(grad / gmax, 0.0, 1.0)
    return stab.astype(np.float32)


def occ_v8_depth(origin_xy: tuple[int, int], pt_xy: tuple[int, int], depth: np.ndarray, floor_mask01: np.ndarray) -> float:
    """
    origin -> pt 선분을 따라 depth 급변(장애물) 정도를 occlusion (0~1)로 계산.
    간단한 샘플링 기반(제품형: 안정/예측 가능)
    """
    ox, oy = origin_xy
    x, y = pt_xy

    # 라인 샘플
    n = 24
    xs = np.linspace(ox, x, n).astype(np.int32)
    ys = np.linspace(oy, y, n).astype(np.int32)

    H, Wimg = depth.shape[:2]
    vals = []
    for xi, yi in zip(xs, ys):
        if 0 <= xi < Wimg and 0 <= yi < H:
            vals.append(float(depth[yi, xi]))
    if len(vals) < 5:
        return 0.0

    # depth 변화량 기반
    diffs = np.abs(np.diff(vals))
    d95 = float(np.percentile(diffs, 95))
    # threshold로 정규화
    occ = np.clip(d95 / max(DEPTH_OCC_THRESHOLD, 1e-6), 0.0, 1.0)
    return float(occ)


def classify_surface_by_depth(dval: float, floor_p20: float, floor_p80: float) -> str:
    """
    바닥 depth 분포(p20~p80) 대비 후보점 depth가 튀면 other로 분류.
    """
    lo = min(floor_p20, floor_p80)
    hi = max(floor_p20, floor_p80)
    if dval < lo or dval > hi:
        return "other"
    return "floor"


def cluster_and_pick(scored: list, cluster_dist: float = 55.0, max_total: int = 6) -> list:
    """
    scored: [(score, (x,y), meta), ...] 정렬된 리스트.
    거리 기반으로 가까운 점은 하나만 남김.
    """
    chosen = []
    for s, pt, meta in scored:
        if len(chosen) >= max_total:
            break
        ok = True
        for _, cpt, _ in chosen:
            if (pt[0] - cpt[0]) ** 2 + (pt[1] - cpt[1]) ** 2 < (cluster_dist ** 2):
                ok = False
                break
        if ok:
            chosen.append((s, pt, meta))
    return chosen


def to_jsonable(obj: Any):
    """numpy 타입/tuple 등을 json dump 가능한 타입으로 변환"""
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def daily_light_area(pt, origin, base_dir_vec, img=None):
    """
    프로토타입용: 시간대(morning/noon/evening)별 '상대 광량' 점수 생성.
    - 지금은 '임의값' 기반이지만, 이후 Solar API 붙이면 여기서 절대광량으로 대체/보정하면 됨.
    반환:
      times: dict
      total: float
    """
    x, y = float(pt[0]), float(pt[1])
    ox, oy = float(origin[0]), float(origin[1])

    # origin에서 가까울수록 밝다(단순 모델) + 전방(base_dir) 방향 보너스
    v = np.array([x - ox, y - oy], dtype=np.float32)
    dist = float(np.linalg.norm(v)) + 1e-6
    v_norm = v / dist

    d = np.array([float(base_dir_vec[0]), float(base_dir_vec[1])], dtype=np.float32)
    dn = d / (float(np.linalg.norm(d)) + 1e-6)

    forward = float(np.clip(np.dot(v_norm, dn), -1.0, 1.0))  # -1~1
    forward01 = (forward + 1.0) * 0.5                       # 0~1

    # 거리 기반 기본 밝기(0~1)
    base = 1.0 / (1.0 + dist / 220.0)

    # 시간대 가중치(임의)
    times = {
        "morning": base * (0.7 + 0.6 * forward01),
        "noon":    base * (0.9 + 0.3 * forward01),
        "evening": base * (0.6 + 0.4 * forward01),
    }
    total = float(times["morning"] + times["noon"] + times["evening"])
    return times, total
