import cv2
import numpy as np
import os

def order_tl_tr_br_bl(pts: np.ndarray) -> np.ndarray:
    pts = pts.astype(np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

def _save_dbg(debug_dir, name, img):
    if debug_dir is None:
        return
    try:
        os.makedirs(debug_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_dir, name), img)
    except Exception:
        pass

def extract_window_corners_edge(img_bgr: np.ndarray, win_bbox, debug_dir=None, tag="window"):
    """
    bbox 내부에서 여러 파라미터로 edge/contour를 시도해 가장 '사각형 같은' 것을 반환
    return: corners4 (4,2) or None
    """
    H, W = img_bgr.shape[:2]
    x, y, w, h = [int(v) for v in win_bbox]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return None

    roi = img_bgr[y0:y1, x0:x1].copy()
    _save_dbg(debug_dir, f"{tag}_roi.png", roi)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 대비 강화(어두운 창/커튼 대응)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # 여러 canny 조합을 자동 시도
    canny_pairs = [
        (20, 60),
        (30, 90),
        (40, 120),
        (60, 180),
    ]

    best_corners = None
    best_score = -1.0
    best_edges = None

    for (t1, t2) in canny_pairs:
        edges = cv2.Canny(gray, t1, t2)

        # 연결 강화
        k = np.ones((5, 5), np.uint8)
        edges2 = cv2.dilate(edges, k, iterations=2)
        edges2 = cv2.morphologyEx(edges2, cv2.MORPH_CLOSE, k, iterations=2)

        contours, _ = cv2.findContours(edges2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        # bbox 내부에서 사각형 후보 찾기
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 300:
                continue

            rect = cv2.minAreaRect(cnt)
            (cx, cy), (rw, rh), ang = rect
            if rw < 10 or rh < 10:
                continue

            rect_area = float(rw * rh)
            if rect_area <= 1e-6:
                continue

            fill = float(area) / rect_area
            ar = max(rw, rh) / (min(rw, rh) + 1e-6)

            # 스코어: 크게 + 채움비율 높게 + 너무 긴거 패널티
            score = area * (0.5 + fill) * (1.0 / (1.0 + 0.25 * max(0.0, ar - 3.0)))

            if score > best_score:
                box = cv2.boxPoints(rect)  # roi coords
                box = box + np.array([x0, y0], dtype=np.float32)  # global coords
                best_corners = order_tl_tr_br_bl(box)
                best_score = score
                best_edges = edges2.copy()

    if best_edges is not None:
        _save_dbg(debug_dir, f"{tag}_edges.png", best_edges)

    return best_corners

def extract_window_corners_hough(img_bgr: np.ndarray, win_bbox, debug_dir=None, tag="window"):
    """
    contour가 안 잡힐 때: HoughLinesP로 선분 모아서 minAreaRect
    """
    H, W = img_bgr.shape[:2]
    x, y, w, h = [int(v) for v in win_bbox]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return None

    # bbox 테두리 에지(ROI 경계) 먹는 문제 방지: 안쪽으로 조금 축소
    margin = int(0.06 * min(w, h))  # 6% 정도
    x0i = x0 + margin
    y0i = y0 + margin
    x1i = x1 - margin
    y1i = y1 - margin
    if x1i <= x0i or y1i <= y0i:
        return None

    roi = img_bgr[y0i:y1i, x0i:x1i].copy()  # ✅ margin ROI 유지
    _save_dbg(debug_dir, f"{tag}_hough_roi.png", roi)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(gray, 30, 120)
    _save_dbg(debug_dir, f"{tag}_hough_edges.png", edges)

    rw = x1i - x0i
    rh = y1i - y0i

    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=60,
        minLineLength=max(25, int(min(rw, rh) * 0.25)),  # ✅ ROI 기준
        maxLineGap=20
    )
    if lines is None:
        return None

    pts = []
    for l in lines:
        x1l, y1l, x2l, y2l = l[0]
        dx = x2l - x1l
        dy = y2l - y1l
        ang = abs(np.degrees(np.arctan2(dy, dx)))

        # 수평(0~15도, 165~180도) 또는 수직(75~105도)만
        is_h = (ang < 15) or (ang > 165)
        is_v = (75 < ang < 105)
        if not (is_h or is_v):
            continue

        pts.append([x1l, y1l])
        pts.append([x2l, y2l])

    if len(pts) < 4:  # ✅ 방어
        return None

    pts = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)

    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect) + np.array([x0i, y0i], dtype=np.float32)  # ✅ global offset
    corners4 = order_tl_tr_br_bl(box)

    # 디버그 라인 시각화 (ROI 좌표)
    if debug_dir is not None:
        vis = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        for l in lines[:80]:
            x1l, y1l, x2l, y2l = l[0]
            cv2.line(vis, (x1l, y1l), (x2l, y2l), (0, 255, 0), 1)
        _save_dbg(debug_dir, f"{tag}_hough_lines.png", vis)

    return corners4
