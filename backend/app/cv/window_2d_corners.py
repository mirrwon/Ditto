import cv2
import numpy as np

def order_corners_tl_tr_br_bl(pts: np.ndarray) -> np.ndarray:
    """
    pts: (4,2) float array
    return: (4,2) ordered as TL, TR, BR, BL
    """
    pts = pts.astype(np.float32)

    s = pts.sum(axis=1)          # x+y
    diff = np.diff(pts, axis=1)  # x-y

    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]

    return np.array([tl, tr, br, bl], dtype=np.float32)

def extract_window_corners_from_mask(mask: np.ndarray) -> np.ndarray:
    """
    mask: HxW (0/255 or 0/1)
    return: (4,2) corners ordered TL,TR,BR,BL in pixel coords
    """
    if mask.dtype != np.uint8:
        mask = mask.astype(np.uint8)
    if mask.max() == 1:
        mask = mask * 255

    # 노이즈 제거 (너무 세게 하면 창문이 깨질 수 있음)
    kernel = np.ones((5, 5), np.uint8)
    clean = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("No contours found in window mask")

    # 가장 큰 영역을 창문으로 가정
    cnt = max(contours, key=cv2.contourArea)
    if cv2.contourArea(cnt) < 100:  # 너무 작으면 실패
        raise ValueError("Window contour too small")

    rect = cv2.minAreaRect(cnt)          # ((cx,cy),(w,h),angle)
    box = cv2.boxPoints(rect)            # 4x2
    box = order_corners_tl_tr_br_bl(box) # TL,TR,BR,BL

    return box
