from __future__ import annotations

import os
from io import BytesIO
from typing import Any, Dict, Optional

from PIL import Image

try:
    from google import genai
except Exception:
    genai = None


def gemini_edit_image(
    *,
    input_image_path: str,
    prompt: str,
    out_path: str,
    model: str = "gemini-3-pro-image-preview",
    api_key_env: str = "GEMINI_API_KEY",
) -> Dict[str, Any]:
    """
    Gemini 이미지 편집 호출 (marker 이미지 기반)
    반환: {"ok": bool, "out_path": str?, "reason": str?}
    """
    if genai is None:
        return {"ok": False, "reason": "google-genai not installed. pip install google-genai"}

    api_key = os.getenv(api_key_env)
    if not api_key:
        return {"ok": False, "reason": f"{api_key_env} missing in environment"}

    if not os.path.exists(input_image_path):
        return {"ok": False, "reason": f"input not found: {input_image_path}"}

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    try:
        client = genai.Client(api_key=api_key)
        img = Image.open(input_image_path)

        response = client.models.generate_content(
            model=model,
            contents=[prompt, img],
        )

        saved = False
        for cand in (response.candidates or []):
            content = getattr(cand, "content", None)
            if not content:
                continue
            for part in (content.parts or []):
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    # ✅ [DEBUG] 저장 전 상태 찍기
                    print("[GEMINI] out_path=", out_path)
                    print("[GEMINI] out_dir=", os.path.dirname(out_path))
                    print("[GEMINI] out_dir exists=", os.path.isdir(os.path.dirname(out_path)))
                    print("[GEMINI] inline.data bytes_len=", len(inline.data) if inline.data else None)

                    out_img = Image.open(BytesIO(inline.data))

                    # ✅ 모드 정규화 (저장 실패/깨짐 방지)
                    if out_img.mode not in ("RGB", "RGBA"):
                        out_img = out_img.convert("RGBA")

                    out_img.save(out_path)

                    # ✅ [DEBUG] 저장 후 상태 찍기
                    print("[GEMINI] saved exists=", os.path.exists(out_path))
                    print("[GEMINI] saved size=", os.path.getsize(out_path) if os.path.exists(out_path) else None)

                    # ✅ 저장 검증 (실제 파일 생성/0바이트 방지)
                    if (not os.path.exists(out_path)) or os.path.getsize(out_path) == 0:
                        return {"ok": False, "reason": f"ai_edit not created or empty: {out_path}"}

                    saved = True
                    break
            if saved:
                break

        if not saved:
            return {"ok": False, "reason": "no image returned from gemini"}

        return {"ok": True, "out_path": out_path}

    except Exception as e:
        return {"ok": False, "reason": f"gemini error: {e}"}

def gemini_inpaint_with_reference(
    *,
    room_image_path: str,
    reference_image_path: Optional[str] = None,
    mask_image_path: str,
    prompt: str,
    out_path: str,
    model: str = "gemini-2.5-flash-image",
    api_key_env: str = "GEMINI_API_KEY",
) -> Dict[str, Any]:

    """
    Gemini 부분 생성(inpaint) + 참조(reference) + 마스크(mask)
    반환: {"ok": bool, "out_path": str?, "reason": str?}
    """
    if genai is None:
        return {"ok": False, "reason": "google-genai not installed. pip install google-genai"}

    api_key = os.getenv(api_key_env)
    if not api_key:
        return {"ok": False, "reason": f"{api_key_env} missing in environment"}

    # room/mask는 필수
    for p, name in [(room_image_path, "room"), (mask_image_path, "mask")]:
        if not os.path.exists(p):
            return {"ok": False, "reason": f"{name} not found: {p}"}

    # reference는 선택 (있을 때만)
    if reference_image_path:
        if not os.path.exists(reference_image_path):
            return {"ok": False, "reason": f"reference not found: {reference_image_path}"}

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    try:
        client = genai.Client(api_key=api_key)

        room_img = Image.open(room_image_path)
        mask_img = Image.open(mask_image_path)

        contents = [prompt, room_img, mask_img]

        if reference_image_path:
            ref_img = Image.open(reference_image_path)
            contents = [prompt, room_img, ref_img, mask_img]

        response = client.models.generate_content(
            model=model,
            contents=contents,
        )

        saved = False
        for cand in (response.candidates or []):
            content = getattr(cand, "content", None)
            if not content:
                continue
            for part in (content.parts or []):
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    out_img = Image.open(BytesIO(inline.data))
                    if out_img.mode not in ("RGB", "RGBA"):
                        out_img = out_img.convert("RGBA")
                    out_img.save(out_path)

                    if (not os.path.exists(out_path)) or os.path.getsize(out_path) == 0:
                        return {"ok": False, "reason": f"out not created or empty: {out_path}"}

                    saved = True
                    break
            if saved:
                break

        if not saved:
            return {"ok": False, "reason": "no image returned from gemini"}

        return {"ok": True, "out_path": out_path}

    except Exception as e:
        return {"ok": False, "reason": f"gemini error: {e}"}
