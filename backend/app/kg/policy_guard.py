"""Minimal policy guard for edit-only MVP.

This is not about 'out of scope'. It's about safety/security:
- prompt injection attempts
- sensitive/high-risk topics (medical/legal/investment)
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


_PHONE = re.compile(r"\b010[- ]?\d{4}[- ]?\d{4}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RID = re.compile(r"\b\d{6}-?\d{7}\b")
_CARDLIKE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def check_policy(question: str, rules: Dict[str, Any], *, is_authenticated: bool = True) -> Dict[str, Any]:
    policy = rules.get("policy") or {}
    q = (question or "").strip()

    # PII (optional but helpful)
    if _PHONE.search(q) or _EMAIL.search(q) or _RID.search(q) or _CARDLIKE.search(q):
        return {"decision": "DENY", "reason": "개인정보가 포함된 요청은 처리할 수 없어요."}

    inj = policy.get("injection_keywords_any") or []
    if any(k and k in q for k in inj):
        return {"decision": "DENY", "reason": "요청을 처리할 수 없어요."}

    sens = policy.get("sensitive_keywords_any") or []
    if any(k and k in q for k in sens):
        return {"decision": "DENY", "reason": "해당 주제는 이 챗봇 범위에서 도와드리기 어려워요."}

    return {"decision": "ALLOW", "reason": "ok"}
