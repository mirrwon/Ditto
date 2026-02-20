"""Rule-based edit request parser (edit_only_v1).

Input: user's Korean text
Output: edit_request_v1 dict
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .edit_schema import empty_edit_request
from .utils import contains_any, normalize_text


def parse_edit_request(
    question: str,
    rules: Dict[str, Any],
    *,
    user_num: Optional[int] = None,
    session_id: Optional[str] = None,
    render_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    slot = rules.get("slot_rules") or {}
    t = normalize_text(question)

    edit = empty_edit_request(session_id=session_id, user_num=user_num, render_id=render_id)
    signals: List[str] = []

    # keep
    keep = slot.get("keep") or {}
    if contains_any(t, keep.get("plant") or []):
        edit["keep"]["plant"] = True
        edit["change"]["plant"]["action"] = "KEEP"
        signals.append("keep_plant")
    if contains_any(t, keep.get("spot") or []):
        edit["keep"]["spot"] = True
        edit["change"]["placement"]["action"] = "KEEP"
        signals.append("keep_spot")

    # placement preference
    pref_map = slot.get("placement_preference") or {}
    pref = _match_enum(t, pref_map)
    if pref:
        edit["change"]["placement"]["action"] = "ADJUST"
        edit["change"]["placement"]["preference"] = pref
        signals.append(f"placement:{pref}")

    # style preset
    style_map = slot.get("style_preset") or {}
    preset = _match_enum(t, style_map)
    if preset:
        edit["change"]["style"]["action"] = "ADJUST"
        edit["change"]["style"]["preset"] = preset
        signals.append(f"style:{preset}")

    # size direction
    size_map = slot.get("size_direction") or {}
    direction = _match_enum(t, size_map)
    if direction:
        edit["change"]["size"]["action"] = "ADJUST"
        edit["change"]["size"]["direction"] = direction
        signals.append(f"size:{direction}")

    # constraints
    cons = slot.get("constraints") or {}
    if contains_any(t, cons.get("has_pet") or []):
        edit["change"]["constraints"]["has_pet"] = True
        signals.append("constraint:pet")
    if contains_any(t, cons.get("has_child") or []):
        edit["change"]["constraints"]["has_child"] = True
        signals.append("constraint:child")
    if contains_any(t, cons.get("allergy_sensitive") or []):
        edit["change"]["constraints"]["allergy_sensitive"] = True
        signals.append("constraint:allergy")

    # confidence heuristic
    if not signals:
        edit["confidence"] = 0.25
    elif len(signals) == 1:
        edit["confidence"] = 0.55
    elif len(signals) == 2:
        edit["confidence"] = 0.70
    else:
        edit["confidence"] = 0.80

    edit["signals"] = signals
    edit["notes"] = t
    debug = {"matched": signals}
    return edit, debug


def needs_clarification(edit: Dict[str, Any], rules: Dict[str, Any]) -> bool:
    """Ask at most one question if confidence is low."""
    try:
        conf = float(edit.get("confidence") or 0.0)
    except Exception:
        conf = 0.0
    max_q = int(((rules.get("edit_flow") or {}).get("max_clarify_questions") or 1))
    return conf < 0.45 and max_q >= 1


def _match_enum(text: str, mapping: Dict[str, List[str]]) -> Optional[str]:
    for enum, kws in mapping.items():
        if contains_any(text, kws or []):
            return enum
    return None
