"""Edit-only chat handler.

This handler ignores Q&A/RAG and focuses on converting user text into EditRequest JSON.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .policy_guard import check_policy
from .edit_parser import parse_edit_request, needs_clarification
from .edit_schema import summarize_edit_request


def handle_chat(
    question: str,
    user_num: int,
    session_id: Optional[str],
    rules: Dict[str, Any],
    loader: Optional[Any] = None,
    *,
    is_authenticated: bool = True,
) -> Dict[str, Any]:
    # 0) policy guard (hard)
    pol = check_policy(question, rules, is_authenticated=is_authenticated)
    if pol.get("decision") != "ALLOW":
        return {
            "intent": "POLICY_DENY",
            "answer": [pol.get("reason", "요청을 처리할 수 없어요.")],
            "followup_question": "",
            "action": None,
            "debug": {"policy": pol},
        }

    # 1) parse edit request
    edit, debug = parse_edit_request(
        question,
        rules,
        user_num=user_num,
        session_id=session_id,
    )

    # 2) clarify at most once
    if needs_clarification(edit, rules):
        q = (rules.get("edit_flow") or {}).get("clarify_question") or "어느 쪽을 바꿀까요? ① 식물 ② 위치 ③ 분위기"
        return {
            "intent": "ASK_CLARIFY",
            "answer": [q],
            "followup_question": q,
            "action": {"type": "ASK_CLARIFY", "payload": {"session_id": session_id}},
            "debug": {"edit": edit, "parser": debug},
        }

    summary = summarize_edit_request(edit, rules)
    return {
        "intent": "EDIT_REQUEST",
        "answer": [summary],
        "followup_question": "",
        "action": {"type": "EDIT_REQUEST", "payload": edit},
        "debug": {"edit": edit, "parser": debug},
    }
