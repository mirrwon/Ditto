"""Schema and helpers for edit_request_v1.

We keep it as a plain dict for easy debugging / JSON serialization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def empty_edit_request(session_id: Optional[str], user_num: Optional[int], render_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "version": "edit_request_v1",
        "session_id": session_id or "unknown",
        "user_num": user_num,
        "render_id": render_id,
        "keep": {"plant": None, "spot": None},
        "change": {
            "plant": {"action": "UNKNOWN", "tags_add": [], "tags_remove": []},
            "placement": {"action": "UNKNOWN", "preference": None},
            "style": {"action": "UNKNOWN", "preset": None, "tags_add": [], "tags_remove": []},
            "size": {"action": "UNKNOWN", "direction": None},
            "constraints": {"has_pet": None, "pet_type": [], "has_child": None, "allergy_sensitive": None},
        },
        "confidence": 0.5,
        "signals": [],
        "notes": "",
    }


def summarize_edit_request(edit: Dict[str, Any], rules: Dict[str, Any]) -> str:
    """Human-readable summary used in the chat reply."""
    parts: List[str] = []
    keep = edit.get("keep") or {}
    ch = edit.get("change") or {}

    if keep.get("plant") is True:
        parts.append("식물은 그대로")
    if keep.get("spot") is True:
        parts.append("위치는 그대로")

    pref = (ch.get("placement") or {}).get("preference")
    if pref:
        m = {
            "near_window": "창가 쪽으로",
            "far_from_window": "창문에서 더 안쪽으로",
            "avoid_direct_sun": "직사광 피해서",
            "more_light": "더 밝게",
            "less_light": "덜 밝게",
        }
        parts.append(m.get(pref, f"위치:{pref}"))

    preset = (ch.get("style") or {}).get("preset")
    if preset:
        m2 = {"modern": "모던/미니멀", "natural": "내추럴", "lush": "풍성", "colorful": "화려/컬러풀"}
        parts.append(f"분위기:{m2.get(preset, preset)}")

    direction = (ch.get("size") or {}).get("direction")
    if direction:
        parts.append("크기: 더 크게" if direction == "bigger" else "크기: 더 작게")

    cs = ch.get("constraints") or {}
    if cs.get("has_pet") is True:
        parts.append("반려동물 고려")
    if cs.get("has_child") is True:
        parts.append("어린이 고려")
    if cs.get("allergy_sensitive") is True:
        parts.append("알러지 고려")

    if not parts:
        return "원하는 수정 방향을 한 줄로 더 말해줘! (예: 창가로 / 더 모던하게 / 식물은 유지)"
    tmpl = ((rules.get("edit_flow") or {}).get("summary_template") or "수정 요청 이해했어: {summary}").strip()
    return tmpl.format(summary=" / ".join(parts))
