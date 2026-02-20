"""Small utilities used across edit-only KG modules."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple


def normalize_text(text: str) -> str:
    return (text or "").strip()


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    t = normalize_text(text).lower()
    for k in keywords:
        if not k:
            continue
        if str(k).lower() in t:
            return True
    return False


def find_first(text: str, keywords: Iterable[str]) -> Optional[str]:
    t = normalize_text(text).lower()
    for k in keywords:
        if not k:
            continue
        if str(k).lower() in t:
            return str(k)
    return None


def safe_json_load(raw: Any) -> Dict[str, Any]:
    """Accept dict or JSON string; return dict or {}."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def dig(d: Dict[str, Any], path: List[str]) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur
