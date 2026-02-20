# MiDas / DPT depth + stability

import numpy as np
import cv2
import torch

def get_depth(img_bgr, device: str):
    try:
        midas = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
        midas.to(device).eval()
        tfm = torch.hub.load("intel-isl/MiDaS", "transforms").small_transform
    except Exception as e:
        print("[WARN] MiDaS load failed:", e)
        return None

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    inp = tfm(rgb).to(device)

    with torch.no_grad():
        pred = midas(inp)
        pred = torch.nn.functional.interpolate(
            pred.unsqueeze(1),
            size=rgb.shape[:2],
            mode="bicubic",
            align_corners=False
        ).squeeze()

    d = pred.detach().cpu().numpy().astype(np.float32)
    dmin, dmax = np.percentile(d, 2), np.percentile(d, 98)
    depth = (d - dmin) / (dmax - dmin + 1e-6)
    return np.clip(depth, 0, 1)

def depth_stability(depth):
    d = cv2.GaussianBlur(depth.astype(np.float32), (0, 0), 1.2)
    gx = cv2.Sobel(d, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(d, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx*gx + gy*gy)
    denom = np.percentile(grad, 95) + 1e-6
    return 1.0 - np.clip(grad / denom, 0, 1)
