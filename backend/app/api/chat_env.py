from __future__ import annotations

from typing import Optional


def env_bool(v: Optional[str], default: bool = False) -> bool:
    """
    문자열 환경변수를 bool로 파싱.
    - True로 인식: "1", "true", "t", "yes", "y", "on"
    - False로 인식: "0", "false", "f", "no", "n", "off"
    - 그 외/None: default
    """
    if v is None:
        return default

    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    return default