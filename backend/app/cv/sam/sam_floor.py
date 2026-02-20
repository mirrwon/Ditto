# SAM 바닥 분할

import numpy as np
import cv2

from segment_anything import sam_model_registry, SamPredictor

def load_sam(device: str, sam_ckpt_path: str):
    sam = sam_model_registry["vit_b"](checkpoint=sam_ckpt_path)
    sam.to(device)
    return SamPredictor(sam)

def segment_floor(image_bgr, predictor: SamPredictor):
    predictor.set_image(image_bgr)
    masks, scores, _ = predictor.predict(point_coords=None, point_labels=None, multimask_output=True)

    h, w, _ = image_bgr.shape
    best, best_area = None, 0

    for mask in masks:
        ys, xs = np.where(mask)
        if len(xs) < 800:
            continue
        if ys.min() < h * 0.35:
            continue
        area = len(xs)
        if area > best_area:
            best_area = area
            best = mask.astype(np.uint8)

    return best

def floor_core(mask, k=19):
    ker = np.ones((k, k), np.uint8)
    return cv2.erode(mask.astype(np.uint8), ker, iterations=1)

def candidates_from_mask(mask, step=18):
    h, w = mask.shape
    pts = []
    for y in range(0, h, step):
        for x in range(0, w, step):
            if mask[y, x]:
                pts.append((x, y))
    return pts

def distance_to_boundary(floor_mask):
    m = (floor_mask > 0).astype(np.uint8) * 255
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    return dist / (dist.max() + 1e-6)

def floor_center(mask):
    ys, xs = np.where(mask > 0)
    return np.array([float(xs.mean()), float(ys.mean())], dtype=np.float32)
