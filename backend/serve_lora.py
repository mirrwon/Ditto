import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from peft import PeftModel
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

EMOTE_SET = {
    "HAPPY",
    "NEEDY",
    "ANNOYED",
    "SASSY",
    "WORRIED",
    "CALM",
    "PROUD",
    "MAGICAL",
}

ANIMATION_SET = {
    "idle",
    "bounce",
    "shake",
    "wiggle",
    "float",
    "sparkle",
    "droop",
    "pout",
    "wave",
    "nod",
}

DEFAULT_SYSTEM_PROMPT = (
    "You generate Korean Tamagotchi-style plant dialogue. "
    "Output MUST be a single JSON object only. No markdown. No extra text. "
    "No emojis or decorative symbols. "
    "Schema: {\"text\": string, \"emote\": one of fixed set, "
    "\"animation\": one of fixed set, \"tags\": string array}."
)


def _parse_allow_origins() -> List[str]:
    raw = os.getenv("ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").strip()
    if not raw:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    if raw == "*":
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]


APP = FastAPI(title="DittoGotchi Lora Inference")
APP.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
MODEL = None
TOKENIZER = None
MAX_INPUT_TOKENS = 3072


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Gemma2 + LoRA adapter")
    parser.add_argument("--base_model", type=str, default="google/gemma-2-9b-it")
    parser.add_argument("--adapter_dir", type=str, required=True)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--max_input_tokens", type=int, default=3072)
    parser.add_argument("--load_in_4bit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--trust_remote_code", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


class ChatMessage(BaseModel):
    role: str
    content: str


class GenerateRequest(BaseModel):
    messages: Optional[List[ChatMessage]] = None
    system_prompt: Optional[str] = None
    user_payload: Optional[Dict[str, Any]] = None
    max_new_tokens: int = Field(default=128, ge=16, le=512)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, gt=0.0, le=1.0)
    repetition_penalty: float = Field(default=1.05, ge=1.0, le=2.0)


class GenerateResponse(BaseModel):
    text: str
    emote: str
    animation: str
    tags: List[str]


def extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                try:
                    return json.loads(chunk)
                except Exception:
                    return None
    return None


def validate_output(obj: Dict[str, Any]) -> GenerateResponse:
    if not isinstance(obj, dict):
        raise ValueError("output is not an object")

    text = obj.get("text")
    emote = obj.get("emote")
    animation = obj.get("animation")
    tags = obj.get("tags")

    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    emote = emote.upper() if isinstance(emote, str) else emote
    if emote not in EMOTE_SET:
        raise ValueError(f"invalid emote: {emote}")
    animation = animation.lower() if isinstance(animation, str) else animation
    if animation not in ANIMATION_SET:
        raise ValueError(f"invalid animation: {animation}")
    if not isinstance(tags, list) or any(not isinstance(x, str) for x in tags):
        raise ValueError("tags must be string list")

    return GenerateResponse(
        text=text.strip(),
        emote=emote,
        animation=animation,
        tags=tags,
    )


def build_fallback_output(raw_text: str) -> GenerateResponse:
    raw = (raw_text or "").strip()
    text = ""

    # 1) Try extracting "text" from any JSON object first.
    parsed = extract_first_json_object(raw)
    if isinstance(parsed, dict):
        candidate = parsed.get("text")
        if isinstance(candidate, str):
            text = candidate.strip()

    # 2) If still empty, salvage from malformed JSON-like strings.
    if not text and raw:
        m = re.search(r'"text"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw)
        if m:
            text = m.group(1).strip().replace('\\"', '"')

    # 3) Keep a stable Korean loading/fallback phrase as a last resort.
    if not text:
        text = "지금은 잠깐 숨 고르는 중이야. 다시 눌러줘."

    # Keep response short and stable for UI even when model output is malformed.
    return GenerateResponse(
        text=text[:120],
        emote="CALM",
        animation="idle",
        tags=["fallback"],
    )


def _merge_system_into_user(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    system_chunks = [str(x.get("content", "")).strip() for x in messages if x.get("role") == "system"]
    non_system = [dict(x) for x in messages if x.get("role") != "system"]

    if not system_chunks:
        return non_system

    system_text = "\n\n".join([x for x in system_chunks if x]).strip()
    if not system_text:
        return non_system

    if non_system and non_system[0].get("role") == "user":
        first = dict(non_system[0])
        first["content"] = f"[SYSTEM]\n{system_text}\n\n{first.get('content', '')}"
        non_system[0] = first
        return non_system

    non_system.insert(0, {"role": "user", "content": f"[SYSTEM]\n{system_text}"})
    return non_system


def build_messages(req: GenerateRequest) -> List[Dict[str, str]]:
    if req.messages and len(req.messages) > 0:
        raw = [{"role": m.role, "content": m.content} for m in req.messages]
        return _merge_system_into_user(raw)

    system_prompt = req.system_prompt or DEFAULT_SYSTEM_PROMPT
    if req.user_payload is None:
        raise ValueError("Either messages or user_payload must be provided")

    user_json = json.dumps(req.user_payload, ensure_ascii=False)
    merged_user = f"[SYSTEM]\n{system_prompt}\n\n{user_json}"
    return [{"role": "user", "content": merged_user}]


def apply_chat_template(messages: List[Dict[str, str]]) -> str:
    if hasattr(TOKENIZER, "apply_chat_template"):
        return TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"<{role}>\n{content}\n</{role}>")
    lines.append("<assistant>\n")
    return "\n".join(lines)


@APP.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}


@APP.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    try:
        messages = build_messages(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        prompt = apply_chat_template(messages)
        inputs = TOKENIZER(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_INPUT_TOKENS,
        )

        device = next(MODEL.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        do_sample = req.temperature > 0.0

        with torch.no_grad():
            outputs = MODEL.generate(
                **inputs,
                max_new_tokens=req.max_new_tokens,
                do_sample=do_sample,
                temperature=req.temperature if do_sample else None,
                top_p=req.top_p if do_sample else None,
                repetition_penalty=req.repetition_penalty,
                eos_token_id=TOKENIZER.eos_token_id,
                pad_token_id=TOKENIZER.pad_token_id,
            )

        gen_ids = outputs[0][inputs["input_ids"].shape[1] :]
        gen_text = TOKENIZER.decode(gen_ids, skip_special_tokens=True).strip()
    except Exception as exc:
        print(f"[LoRA][generate] runtime failure: {exc}")
        return build_fallback_output("")

    parsed = extract_first_json_object(gen_text)
    if parsed is None:
        print("[LoRA][generate] no_json_object -> fallback")
        return build_fallback_output(gen_text)

    try:
        return validate_output(parsed)
    except Exception as exc:
        print(f"[LoRA][generate] invalid_schema -> fallback: {exc}")
        return build_fallback_output(gen_text)


def load_model(base_model: str, adapter_dir: str, trust_remote_code: bool, load_in_4bit: bool) -> None:
    global MODEL, TOKENIZER

    TOKENIZER = AutoTokenizer.from_pretrained(base_model, trust_remote_code=trust_remote_code)
    if TOKENIZER.pad_token is None:
        TOKENIZER.pad_token = TOKENIZER.eos_token

    quant_config = None
    if load_in_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        device_map="auto",
        trust_remote_code=trust_remote_code,
        quantization_config=quant_config,
        torch_dtype=torch.bfloat16,
    )

    MODEL = PeftModel.from_pretrained(base, adapter_dir)
    MODEL.eval()


def main() -> None:
    args = parse_args()
    if not os.path.isdir(args.adapter_dir):
        raise FileNotFoundError(f"adapter_dir not found: {args.adapter_dir}")

    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ["HUGGINGFACE_HUB_TOKEN"] = hf_token

    global MAX_INPUT_TOKENS
    MAX_INPUT_TOKENS = int(args.max_input_tokens)

    load_model(
        base_model=args.base_model,
        adapter_dir=args.adapter_dir,
        trust_remote_code=args.trust_remote_code,
        load_in_4bit=args.load_in_4bit,
    )

    _warmup()

    uvicorn.run(APP, host=args.host, port=args.port, workers=args.workers)


def _warmup() -> None:
    """서버 시작 직후 더미 추론으로 CUDA 커널 워밍업."""
    print("[warmup] CUDA kernel warmup 시작...")
    try:
        dummy = "[SYSTEM]\nYou are a plant tamagotchi.\n\n{\"action\":\"idle\"}"
        inputs = TOKENIZER(dummy, return_tensors="pt", truncation=True, max_length=64)
        device = next(MODEL.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            MODEL.generate(**inputs, max_new_tokens=16, do_sample=False)
        print("[warmup] 완료 - 서버 준비됨")
    except Exception as e:
        print(f"[warmup] 실패 (무시하고 계속): {e}")


if __name__ == "__main__":
    main()
