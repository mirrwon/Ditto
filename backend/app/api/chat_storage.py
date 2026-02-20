import json
from typing import Any, Dict, Optional

import redis

from app.db.redis_client import get_redis as get_shared_redis

# Fallback in-memory (Redis down 대비)
USER_STATE: Dict[str, Dict[str, Any]] = {}
USER_CTX: Dict[str, Dict[str, Any]] = {}


def _decode_text(value: Any, encoding: str = "utf-8") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            return value.decode(encoding, errors="replace")
    return str(value)


def _safe_json_loads(raw: Any) -> Dict[str, Any]:
    text = _decode_text(raw).strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _redis_client() -> Optional[redis.Redis]:
    return get_shared_redis()


def _rk_ctx(client_key: str) -> str:
    return f"user_ctx:{client_key}"


def _rk_state(client_key: str) -> str:
    return f"user_state:{client_key}"


def _rget_json(r: redis.Redis, key: str) -> Dict[str, Any]:
    raw = r.get(key)
    if not raw:
        return {}
    return _safe_json_loads(raw)


def _rset_json(r: redis.Redis, key: str, obj: Dict[str, Any], ttl_sec: Optional[int] = None):
    payload = json.dumps(obj, ensure_ascii=False)
    if ttl_sec and ttl_sec > 0:
        r.setex(key, int(ttl_sec), payload)
    else:
        r.set(key, payload)


def get_user_ctx(client_key: str) -> Dict[str, Any]:
    r = _redis_client()
    if r is not None:
        return _rget_json(r, _rk_ctx(client_key))
    v = USER_CTX.get(client_key, {})
    return v if isinstance(v, dict) else {}


def set_user_ctx(client_key: str, updates: Dict[str, Any], ttl_sec: Optional[int] = None):
    r = _redis_client()
    if r is not None:
        cur = _rget_json(r, _rk_ctx(client_key))
        if isinstance(updates, dict):
            cur.update(updates)
        _rset_json(r, _rk_ctx(client_key), cur, ttl_sec=ttl_sec)
        return

    USER_CTX.setdefault(client_key, {})
    if isinstance(updates, dict):
        USER_CTX[client_key].update(updates)


def get_user_state(client_key: str) -> Dict[str, Any]:
    r = _redis_client()
    if r is not None:
        return _rget_json(r, _rk_state(client_key))
    v = USER_STATE.get(client_key, {})
    return v if isinstance(v, dict) else {}


def set_user_state(client_key: str, updates: Dict[str, Any], ttl_sec: Optional[int] = None):
    r = _redis_client()
    if r is not None:
        cur = _rget_json(r, _rk_state(client_key))
        if isinstance(updates, dict):
            cur.update(updates)
        _rset_json(r, _rk_state(client_key), cur, ttl_sec=ttl_sec)
        return

    USER_STATE.setdefault(client_key, {})
    if isinstance(updates, dict):
        USER_STATE[client_key].update(updates)
