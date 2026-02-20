import os
import cv2
import numpy as np
import torch

from segment_anything import sam_model_registry, SamPredictor
from app.config import SAM_CKPT, MODEL_DIR

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

_sam = None
_predictor = None


def load_sam():
    """
    ✅ SAM ViT-B 싱글톤 로드
    - checkpoint 경로는 app/config.py의 SAM_CKPT를 따른다.
    """
    global _sam, _predictor

    if _predictor is not None:
        return _predictor

    print("[SAM] __file__ =", __file__)
    print("[SAM] MODEL_DIR =", MODEL_DIR)
    print("[SAM] SAM_CKPT  =", SAM_CKPT)

    if not os.path.exists(SAM_CKPT):
        raise FileNotFoundError(
            f"[SAM] checkpoint not found:\n{SAM_CKPT}\n\n"
            f"✅ 해결:\n"
            f"1) 파일이 실제로 존재하는지 확인\n"
            f"   -> {MODEL_DIR}\\sam_vit_b.pth\n"
            f"2) 파일명이 sam_vit_b.pth로 맞는지 확인\n"
        )

    _sam = sam_model_registry["vit_b"](checkpoint=SAM_CKPT)
    _sam.to(device=DEVICE)
    _predictor = SamPredictor(_sam)

    print(f"[SAM] loaded: vit_b on {DEVICE}")
    return _predictor


def segment_floor(image_bgr: np.ndarray):
    """
    입력: BGR 이미지
    출력: (mask_255, contour)
      - mask_255: uint8 (0 or 255)
    """
    predictor = load_sam()
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    predictor.set_image(image_rgb)

    H, W = image_rgb.shape[:2]

    # ✅ 바닥을 하단 중앙 기반으로 안정적으로 찍는다.
    input_points = np.array([
        [W * 0.50, H * 0.85],
        [W * 0.30, H * 0.92],
        [W * 0.70, H * 0.92],
    ], dtype=np.float32)
    input_labels = np.array([1, 1, 1], dtype=np.int32)

    masks, scores, _ = predictor.predict(
        point_coords=input_points,
        point_labels=input_labels,
        multimask_output=True
    )

    if masks is None or len(masks) == 0:
        return None, None

    # 가장 넓은 마스크 선택
    areas = [int(np.sum(m)) for m in masks]
    idx = int(np.argmax(areas))
    mask_255 = (masks[idx].astype(np.uint8)) * 255

    contours, _ = cv2.findContours(mask_255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea) if contours else None

    return mask_255, contour


def get_floor_center(mask_255: np.ndarray):
    ys, xs = np.where(mask_255 > 0)
    if len(xs) == 0:
        return None
    return np.array([float(xs.mean()), float(ys.mean())], dtype=np.float32)
