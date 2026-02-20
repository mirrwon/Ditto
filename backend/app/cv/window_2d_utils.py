import cv2
import numpy as np

def order_tl_tr_br_bl(pts: np.ndarray) -> np.ndarray:
    pts = pts.astype(np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

def contour_to_4corners(cnt) -> np.ndarray:
    rect = cv2.minAreaRect(cnt)
    box = cv2.boxPoints(rect)            # (4,2)
    box = order_tl_tr_br_bl(box)
    return box

def mask_to_largest_contour(mask: np.ndarray):
    if mask.dtype != np.uint8:
        mask = mask.astype(np.uint8)
    if mask.max() == 1:
        mask = mask * 255

    kernel = np.ones((5, 5), np.uint8)
    clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    cnt = max(contours, key=cv2.contourArea)
    if cv2.contourArea(cnt) < 200:
        return None
    return cnt
