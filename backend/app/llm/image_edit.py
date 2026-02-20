# 원본 이미지 기반 "좌표 위치 합성" 유틸 (text-to-image 금지)
# + plant PNG가 없을 때 자동 placeholder 생성 지원

from __future__ import annotations

import os
import cv2
from typing import Any, Dict, Optional, Tuple, Union

from PIL import Image, ImageDraw


PointLike = Union[Tuple[float, float], Dict[str, float], list]


def _parse_best_point(obj: Any) -> Optional[Tuple[float, float]]:
    if obj is None:
        return None

    # list/tuple: [x,y]
    if isinstance(obj, (list, tuple)) and len(obj) >= 2:
        try:
            return float(obj[0]), float(obj[1])
        except Exception:
            return None

    if isinstance(obj, dict):
        # ✅ 1) 가장 중요한 케이스: {"pt":[x,y]} / {"pt":(x,y)} / {"pt":{"x":..,"y":..}}
        if "pt" in obj:
            v = obj.get("pt")
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                try:
                    return float(v[0]), float(v[1])
                except Exception:
                    return None
            if isinstance(v, dict):
                if "x" in v and "y" in v:
                    try:
                        return float(v["x"]), float(v["y"])
                    except Exception:
                        return None

        # ✅ 2) 호환: {"x":..,"y":..} / {"cx":..,"cy":..} / {"px":..,"py":..}
        for kx, ky in [("x", "y"), ("cx", "cy"), ("px", "py")]:
            if kx in obj and ky in obj:
                try:
                    return float(obj[kx]), float(obj[ky])
                except Exception:
                    return None

    return None


def _to_pixel_xy(pt: Tuple[float, float], width: int, height: int) -> Tuple[int, int]:
    """
    pt가 정규화(0~1)일 수도, 픽셀일 수도 있으니 안전 변환.
    - 0~1 범위면 정규화로 보고 곱함
    - 그 외는 픽셀로 취급
    """
    x, y = pt
    if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
        return int(round(x * width)), int(round(y * height))
    return int(round(x)), int(round(y))


def _load_rgba(path: str) -> Image.Image:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img


def _resize_keep_aspect(img: Image.Image, target_w: int) -> Image.Image:
    if target_w <= 0:
        return img
    w, h = img.size
    if w == 0:
        return img
    scale = target_w / float(w)
    target_h = max(1, int(round(h * scale)))
    return img.resize((target_w, target_h), resample=Image.LANCZOS)


def ensure_placeholder_plant_png(path: str, size: int = 512) -> str:
    """
    plant PNG가 없을 때도 합성이 '항상' 되도록 간단한 placeholder 식물 PNG를 생성한다.
    - 투명 배경 + 화분 + 잎(초록) 몇 장
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return path

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # pot
    pot_w = int(size * 0.45)
    pot_h = int(size * 0.20)
    pot_x0 = (size - pot_w) // 2
    pot_y0 = int(size * 0.68)
    pot_x1 = pot_x0 + pot_w
    pot_y1 = pot_y0 + pot_h
    d.rounded_rectangle([pot_x0, pot_y0, pot_x1, pot_y1], radius=int(size * 0.04), fill=(130, 90, 60, 220))

    # soil
    soil_h = int(pot_h * 0.25)
    d.rectangle([pot_x0 + int(pot_w * 0.08), pot_y0, pot_x1 - int(pot_w * 0.08), pot_y0 + soil_h], fill=(80, 55, 35, 220))

    # leaves (simple ellipses)
    cx = size // 2
    base_y = pot_y0 + soil_h
    for i, (dx, dy, lw, lh, alpha) in enumerate([
        (-int(size*0.10), -int(size*0.20), int(size*0.22), int(size*0.40), 200),
        (0,              -int(size*0.26), int(size*0.24), int(size*0.46), 210),
        (int(size*0.10), -int(size*0.20), int(size*0.22), int(size*0.40), 200),
    ]):
        x0 = cx + dx - lw // 2
        y0 = base_y + dy - lh // 2
        x1 = x0 + lw
        y1 = y0 + lh
        d.ellipse([x0, y0, x1, y1], fill=(40, 170, 70, alpha))
        # mid vein
        d.line([( (x0+x1)//2, y0+int(lh*0.15) ), ( (x0+x1)//2, y1-int(lh*0.15) )], fill=(230, 255, 230, 90), width=max(1, int(size*0.008)))

    img.save(path)
    return path


def composite_plant_on_original(
    original_image_path: str,
    best_point_obj: Any,
    out_path: str,
    plant_png_path: Optional[str] = None,
    *,
    plant_width_ratio: float = 0.22,
    anchor: str = "bottom_center",
    add_green_dot: bool = True,
    dot_radius_ratio: float = 0.012,
) -> Dict[str, Any]:
    """
    원본 이미지 위에 식물 PNG를 best_point 좌표에 합성해서 out_path로 저장.
    - plant_png_path가 없거나 파일이 없으면: 식물 합성은 생략하고 (선택) 초록 점만 찍음.
      (원하면 ensure_placeholder_plant_png로 미리 생성해서 넣어주면 '항상 식물' 가능)
    - anchor:
        - "bottom_center": 식물 이미지의 아래 중앙을 좌표에 맞춤 (추천)
        - "center": 식물 이미지 중심을 좌표에 맞춤
    반환: {"ok": bool, "out_path": str, "used_plant": bool, "pixel_xy": (x,y)}
    """
    if not os.path.exists(original_image_path):
        return {"ok": False, "reason": f"original not found: {original_image_path}"}

    base = _load_rgba(original_image_path)
    w, h = base.size

    pt = _parse_best_point(best_point_obj)
    if pt is None:
        base.save(out_path)
        return {"ok": False, "reason": "best_point missing", "out_path": out_path, "used_plant": False}

    px, py = _to_pixel_xy(pt, w, h)

    # (선택) 초록 점 마커
    if add_green_dot:
        dot_r = max(2, int(round(min(w, h) * dot_radius_ratio)))
        _draw_green_dot(base, (px, py), dot_r)

    used_plant = False

    # --- ✅ marker-only mode (PIL 기반, 정상 동작) ---
    if not plant_png_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        base.save(out_path)
        return {
            "ok": True,
            "out_path": out_path,
            "used_plant": False,
            "pixel_xy": (px, py),
        }

    # ✅ 1) plant_png_path가 없거나 파일이 없으면 placeholder를 자동으로 만든다
    if (not plant_png_path) or (not os.path.exists(plant_png_path)):
        # out_path 폴더 옆에 placeholder를 만들어서 항상 합성되게
        ph_path = os.path.join(os.path.dirname(out_path), "_placeholder_plant.png")
        plant_png_path = ensure_placeholder_plant_png(ph_path, size=512)

    # ✅ 2) 이제는 무조건 plant_png_path가 존재한다고 가정하고 합성
    if plant_png_path and os.path.exists(plant_png_path):
        plant = _load_rgba(plant_png_path)

        target_w = max(40, int(round(w * plant_width_ratio)))
        plant = _resize_keep_aspect(plant, target_w)

        pw, ph = plant.size
        if anchor == "center":
            left = px - pw // 2
            top = py - ph // 2
        else:
            left = px - pw // 2
            top = py - ph

        # ✅ alpha_composite는 음수 좌표에서 문제날 수 있어서 0~로 클램프 (안전)
        left = max(0, min(int(left), w - pw))
        top = max(0, min(int(top), h - ph))

        base.alpha_composite(plant, (left, top))
        used_plant = True


    base.save(out_path)
    return {"ok": True, "out_path": out_path, "used_plant": used_plant, "pixel_xy": (px, py)}


def _draw_green_dot(img: Image.Image, center: Tuple[int, int], r: int) -> None:
    cx, cy = center
    pix = img.load()
    w, h = img.size
    rr = r * r
    for y in range(cy - r, cy + r + 1):
        if y < 0 or y >= h:
            continue
        dy = y - cy
        for x in range(cx - r, cx + r + 1):
            if x < 0 or x >= w:
                continue
            dx = x - cx
            if dx * dx + dy * dy <= rr:
                pix[x, y] = (0, 255, 0, 180)