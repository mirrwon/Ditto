import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# ⚠️ 중요:
# - 여기서 OpenAI 클라이언트를 "전역으로" 만들지 않는다.
# - load_dotenv()도 "안전하게" 여기서도 한 번 호출해준다(중복 호출 OK).
# - 클라이언트는 get_client()로 지연 생성한다.

_client = None  # type: ignore


def get_client():
    global _client
    if _client is None:
        load_dotenv()  # .env가 아직 로드 안 된 경우 대비
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Check your .env location and loading order.")

        # OpenAI SDK (new style)
        from openai import OpenAI  # import도 지연: 서버 부팅 안정성 ↑

        _client = OpenAI(api_key=api_key)
    return _client


def judge_with_gpt_4o_mini(
    *,
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    Ditto 판단용 GPT 호출 (gpt-4o-mini)
    - model은 env DITTO_GPT_MODEL 우선, 없으면 gpt-4o-mini
    - 서버 부팅 안정화를 위해 client는 lazy init
    """
    client = get_client()

    load_dotenv()
    model_name = model or os.getenv("DITTO_GPT_MODEL", "gpt-4o-mini")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Responses API 사용 (권장)
    resp = client.responses.create(
        model=model_name,
        input=messages,
        temperature=temperature,
    )

    # 텍스트만 뽑기
    text = ""
    try:
        # SDK 버전에 따라 output_text가 있거나 parsing 방식이 다를 수 있음
        text = getattr(resp, "output_text", "") or ""
        if not text:
            # fallback: output 구조에서 텍스트 조립
            for item in getattr(resp, "output", []) or []:
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", None) in ("output_text", "text"):
                        text += getattr(c, "text", "") or ""
    except Exception:
        pass

    return {
        "model": model_name,
        "text": text.strip(),
        "raw": None,  # 필요하면 resp를 저장하도록 바꿔도 됨(지금은 직렬화 이슈 방지)
    }
