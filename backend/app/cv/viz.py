# 시각화

import cv2
import numpy as np

def draw_debug(
    image,
    floor_mask=None,
    windows=None,
    light_map=None,
    best_point=None,
    save_path="results/result_latest_viz.png"
):
    vis = image.copy()

    # 1) 바닥 (RED)
    if floor_mask is not None:
        fm = floor_mask.astype(bool)
        red = np.zeros_like(vis, dtype=np.uint8)
        red[:, :, 2] = 255
        vis = np.where(
            fm[..., None],
            vis.astype(np.float32) * 0.6 + red.astype(np.float32) * 0.4,
            vis
        )

    # 2) 창틀 (YELLOW)
    if windows:
        for (x1, y1, x2, y2) in windows:
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2)

    # 3) 광량 히트맵 (BLUE-ish via COLORMAP_JET)
    if light_map is not None:
        lm = light_map.astype(np.float32)
        if lm.max() > 0:
            heat = cv2.normalize(lm, None, 0, 255, cv2.NORM_MINMAX)
            heat = heat.astype(np.uint8)
            heat = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
            vis = cv2.addWeighted(vis.astype(np.uint8), 0.7, heat, 0.3, 0)

    # 4) 추천 위치 (GREEN)
    if best_point is not None:
        x, y = best_point
        cv2.circle(vis, (int(x), int(y)), 10, (0, 255, 0), -1)

    vis = np.clip(vis, 0, 255).astype(np.uint8)
    cv2.imwrite(save_path, vis)
