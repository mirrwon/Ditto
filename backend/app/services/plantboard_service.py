import os
import json
import time
import base64
import uuid
import re
import hashlib
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from app.llm.gemini.gemini_image_edit import gemini_edit_image
from app.config import PLANTS_DIR

LORA_SERVER_URL = os.getenv("LORA_SERVER_URL", "http://localhost:8000")
LORA_TIMEOUT_SEC = int(os.getenv("LORA_TIMEOUT_SEC", "12"))
LORA_MAX_NEW_TOKENS = int(os.getenv("LORA_MAX_NEW_TOKENS", "48"))
LORA_TEMPERATURE = float(os.getenv("LORA_TEMPERATURE", "0.0"))
LORA_TOP_P = float(os.getenv("LORA_TOP_P", "0.9"))
LORA_SYSTEM_PROMPT = (
    "You generate Korean Tamagotchi-style plant dialogue. "
    "Output MUST be a single JSON object only. No markdown. No extra text. "
    "Schema exactly: {\"text\":\"...\",\"emote\":\"HAPPY|NEEDY|ANNOYED|SASSY|WORRIED|CALM|PROUD|MAGICAL\","
    "\"animation\":\"idle|bounce|shake|wiggle|float|sparkle|droop|pout|wave|nod\",\"tags\":[\"...\"]}"
)

# 충돌 없는 독립 저장 경로
# Using 'plantboard_store' to avoid collision with other team members' 'data' folders
STORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "plantboard_store")
PLANTS_FILE = os.path.join(STORE_DIR, "user_plants.json")
LOGS_FILE = os.path.join(STORE_DIR, "plant_logs.json")

TAMAGOTCHI_PIXEL_PROMPT = (
    "Transform this interior photo into 1990s tamagotchi-style pixel art. "
    "Moderate pixelation with visible 6-10px pixel blocks (not overly chunky). "
    "Limited palette (8-14 colors). "
    "Muted pastel colors with reduced saturation (low to medium saturation). "
    "Soft, slightly desaturated tones - avoid bright or neon colors. "
    "Clean 1-2px outlines, simplified shapes, minimal texture. "
    "Subtle light/shadow blocks (no gradients). "
    "Cute cozy room vibe, soft nostalgic 90s digital aesthetic. "
    "No blur, no gradients, no noise, no halftone, no dithering."
)


# Ensure directory exists
os.makedirs(STORE_DIR, exist_ok=True)

def _load_json(filepath: str, default_val: any):
    if not os.path.exists(filepath):
        return default_val
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_val

def _save_json(filepath: str, data: any):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[PlantBoard] Save Error: {e}")

def _process_base64_image(image_data: str, prefix: str = "img") -> str:
    """
    Base64 이미지를 파일로 저장하고 접근 가능한 URL을 반환합니다.
    이미 URL 형태일 경우 그대로 반환합니다.
    """
    if not image_data or not isinstance(image_data, str):
        return image_data
    
    # 이미 URL인 경우 (http, /plants/ 등) 처리 생략
    if image_data.startswith(("http", "/api", "/plants", "/uploads", "/results")):
        return image_data
    
    # Base64 패턴 확인 (data:image/png;base64,...)
    match = re.match(r"data:image/(\w+);base64,(.*)", image_data)
    if not match:
        return image_data
    
    ext = match.group(1)
    base64_str = match.group(2)
    
    try:
        # 고유 파일명 생성
        filename = f"{prefix}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(PLANTS_DIR, filename)
        
        # 디렉터리 보장
        os.makedirs(PLANTS_DIR, exist_ok=True)
        
        # 파일로 저장
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(base64_str))
            
        # 프론트엔드에서 접근 가능한 절대 경로 반환
        return f"/plants/{filename}"
    except Exception as e:
        print(f"[PlantBoard] Image Process Error: {e}")
        return image_data

def _save_base64_to_file(image_data: str, prefix: str = "img") -> Optional[str]:
    if not image_data or not isinstance(image_data, str):
        return None
    match = re.match(r"data:image/(\w+);base64,(.*)", image_data)
    if not match:
        return None
    ext = match.group(1)
    base64_str = match.group(2)
    try:
        filename = f"{prefix}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(PLANTS_DIR, filename)
        os.makedirs(PLANTS_DIR, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(base64_str))
        return filepath
    except Exception as e:
        print(f"[PlantBoard] Base64 Save Error: {e}")
        return None

def _download_image_to_file(image_url: str, prefix: str = "room") -> Optional[str]:
    try:
        parsed = urlparse(image_url)
        ext = os.path.splitext(parsed.path)[1] or ".png"
        url_hash = hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:12]
        filename = f"{prefix}_{url_hash}{ext}"
        filepath = os.path.join(PLANTS_DIR, filename)
        if os.path.exists(filepath):
            return filepath
        os.makedirs(PLANTS_DIR, exist_ok=True)
        req = Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp, open(filepath, "wb") as out:
            out.write(resp.read())
        return filepath
    except Exception as e:
        print(f"[PlantBoard] Download Error: {e}")
        return None

def _generate_pixel_image_from_url(image_url: str) -> Dict[str, str]:
    if not image_url:
        return {"ok": False, "reason": "image_url missing"}

    input_path = None
    if image_url.startswith("data:image/"):
        input_path = _save_base64_to_file(image_url, "room")
    elif image_url.startswith(("http://", "https://")):
        input_path = _download_image_to_file(image_url, "room")
    elif image_url.startswith(("/plants/", "/uploads/", "/results/")):
        input_path = os.path.join(PLANTS_DIR, os.path.basename(image_url))
    else:
        input_path = image_url if os.path.exists(image_url) else None

    if not input_path or not os.path.exists(input_path):
        return {"ok": False, "reason": "input image not found"}

    base = os.path.splitext(os.path.basename(input_path))[0]
    out_filename = f"{base}_pixel.png"
    out_path = os.path.join(PLANTS_DIR, out_filename)

    res = gemini_edit_image(
        input_image_path=input_path,
        prompt=TAMAGOTCHI_PIXEL_PROMPT,
        out_path=out_path,
    )

    if not res.get("ok"):
        return {"ok": False, "reason": res.get("reason", "gemini failed")}

    return {"ok": True, "url": f"/plants/{out_filename}"}


def generate_tamagotchi_room_pixel_image(username: str, image_url: str, plant_id: Optional[str] = None) -> Dict[str, str]:
    res = _generate_pixel_image_from_url(image_url)
    if not res.get("ok"):
        return res

    pixel_url = res["url"]
    if plant_id and username:
        try:
            all_data = _load_json(PLANTS_FILE, {})
            user_list = all_data.get(username, [])
            updated = None
            for p in user_list:
                if p.get("id") == plant_id:
                    p["roomImagePixelUrl"] = pixel_url
                    updated = p
                    break
            all_data[username] = user_list
            _save_json(PLANTS_FILE, all_data)
            return {"ok": True, "url": pixel_url, "plant": updated}
        except Exception as e:
            print(f"[PlantBoard] Save Pixel Error: {e}")

    return {"ok": True, "url": pixel_url}


def generate_tamagotchi_room_pixel_images_for_user(username: str, force: bool = False) -> Dict[str, Any]:
    all_data = _load_json(PLANTS_FILE, {})
    user_list = all_data.get(username, [])
    updated_list = []
    failures = []

    for p in user_list:
        room_url = p.get("roomImageUrl")
        if not room_url:
            continue
        if p.get("roomImagePixelUrl") and not force:
            updated_list.append(p)
            continue

        res = _generate_pixel_image_from_url(room_url)
        if res.get("ok"):
            p["roomImagePixelUrl"] = res["url"]
            updated_list.append(p)
        else:
            failures.append({"id": p.get("id"), "reason": res.get("reason")})

    all_data[username] = user_list
    _save_json(PLANTS_FILE, all_data)

    return {"ok": True, "items": user_list, "failures": failures}

# --- Plants ---

def get_user_plants(username: str) -> List[dict]:
    # Structure: { username: [ {id, name, ...} ] }
    all_data = _load_json(PLANTS_FILE, {})
    return all_data.get(username, [])

def add_user_plant(username: str, plant_data: dict) -> dict:
    all_data = _load_json(PLANTS_FILE, {})
    user_list = all_data.get(username, [])
    
    # Image processing
    if "coverUrl" in plant_data:
        plant_data["coverUrl"] = _process_base64_image(plant_data["coverUrl"], "plant")
    
    # Simple ID generation
    new_id = f"plant_{int(time.time())}_{len(user_list)}"
    plant_data["id"] = new_id
    plant_data["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    user_list.append(plant_data)
    all_data[username] = user_list
    _save_json(PLANTS_FILE, all_data)
    return plant_data

# --- Logs ---

def get_plant_logs(username: str) -> List[dict]:
    # Structure: { username: [ {id, plant_id, action, date...} ] }
    all_data = _load_json(LOGS_FILE, {})
    user_logs = all_data.get(username, [])
    
    # Sort by date desc
    user_logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return user_logs

def add_plant_log(username: str, log_data: dict) -> dict:
    all_data = _load_json(LOGS_FILE, {})
    user_logs = all_data.get(username, [])
    
    # Image processing
    if "imageUrl" in log_data:
        log_data["imageUrl"] = _process_base64_image(log_data["imageUrl"], "log")
    
    new_id = f"log_{int(time.time())}_{len(user_logs)}"
    log_data["id"] = new_id
    # Ensure date exists
    if "date" not in log_data:
        log_data["date"] = time.strftime("%Y-%m-%d")
        
    user_logs.insert(0, log_data) # Prepend
    all_data[username] = user_logs
    _save_json(LOGS_FILE, all_data)
    return log_data

def call_lora_dialogue(plant: dict, triggers: list = None, season: str = None) -> dict:
    import datetime
    if triggers is None:
        triggers = []
    if season is None:
        month = datetime.datetime.now().month
        if month in (3, 4, 5):
            season = "spring"
        elif month in (6, 7, 8):
            season = "summer"
        elif month in (9, 10, 11):
            season = "fall"
        else:
            season = "winter"

    base_payload = {
        "system_prompt": LORA_SYSTEM_PROMPT,
        "user_payload": {
            "plant": {
                "id": plant.get("id", ""),
                "name": plant.get("name", ""),
                "soul": plant.get("soul", ""),
            },
            "season": season,
            "triggers": triggers,
        },
        "temperature": LORA_TEMPERATURE,
        "top_p": LORA_TOP_P,
    }

    # Retry once with shorter generation when schema validation(422) fails.
    for max_new_tokens in (LORA_MAX_NEW_TOKENS, max(24, LORA_MAX_NEW_TOKENS // 2)):
        payload = dict(base_payload)
        payload["max_new_tokens"] = int(max_new_tokens)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(
            f"{LORA_SERVER_URL}/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=LORA_TIMEOUT_SEC) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return {"ok": True, **result}
        except HTTPError as e:
            # 422 means model output schema mismatch; retry once with shorter output.
            try:
                detail = e.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(e)
            print(f"[LoRA] call failed: HTTP {e.code} - {detail}")
            if e.code != 422:
                return {"ok": False, "reason": f"HTTP {e.code}: {detail}"}
        except URLError as e:
            print(f"[LoRA] call failed: {e}")
            return {"ok": False, "reason": str(e)}
        except Exception as e:
            print(f"[LoRA] call failed: {e}")
            return {"ok": False, "reason": str(e)}

    return {"ok": False, "reason": "LoRA output schema invalid (422) after retry"}


def delete_plant_log(username: str, log_id: str) -> bool:
    all_data = _load_json(LOGS_FILE, {})
    user_logs = all_data.get(username, [])
    
    initial_len = len(user_logs)
    user_logs = [log for log in user_logs if log.get("id") != log_id]
    
    if len(user_logs) != initial_len:
        all_data[username] = user_logs
        _save_json(LOGS_FILE, all_data)
        return True
    return False
