import numpy as np
import math

def make_K_from_fov(W: int, H: int, fov_deg: float = 65.0):
    cx = W * 0.5
    cy = H * 0.5
    fov = math.radians(fov_deg)
    fx = (W * 0.5) / math.tan(fov * 0.5)
    fy = fx
    K = np.array([
        [fx, 0.0, cx],
        [0.0, fy, cy],
        [0.0, 0.0, 1.0]
    ], dtype=np.float32)
    return K
