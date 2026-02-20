import os, json, time
from app.config import WEIGHTS_PATH
from app.config import (
    DEPTH_OCC_THRESHOLD,
    OCCLUSION_STRENGTH_V7,
    OCCLUSION_WEIGHT_V8,
)

# ===== 기본 scoring weights (학습됨) =====
DEFAULT_W = {
    "LIGHT": 0.68,
    "WALL":  0.16,
    "PATH":  0.55,
    "STAB":  0.25,
}

# learning rates
LR = {
    "PATH": 0.10,
    "OCC":  0.15,
    "WALL": 0.10,
    "LIGHT":0.05,
    "STAB": 0.05,
}

def load_state(reset: bool = False, occ_mode: str = "v8"):
    """
    반환:
      state = {
        "W": {...},
        "occ_mode": "v7"|"v8",
        "OCCLUSION_STRENGTH_V7": float,
        "OCCLUSION_WEIGHT_V8": float,
        "DEPTH_OCC_THRESHOLD": float
      }
    """
    state = {
        "W": dict(DEFAULT_W),
        "occ_mode": occ_mode,
        "OCCLUSION_STRENGTH_V7": float(OCCLUSION_STRENGTH_V7),
        "OCCLUSION_WEIGHT_V8": float(OCCLUSION_WEIGHT_V8),
        "DEPTH_OCC_THRESHOLD": float(DEPTH_OCC_THRESHOLD),
    }

    if reset:
        return state

    if not os.path.exists(WEIGHTS_PATH):
        return state

    try:
        if os.path.getsize(WEIGHTS_PATH) == 0:
            return state
    except:
        return state

    try:
        with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return state

    w_loaded = data.get("W", {})
    if isinstance(w_loaded, dict):
        for k, v in w_loaded.items():
            if k in state["W"]:
                try:
                    state["W"][k] = float(v)
                except:
                    pass

    # OCC params는 파일에서만 로드(occ_mode는 코드/요청이 우선)
    for k in ["OCCLUSION_STRENGTH_V7", "OCCLUSION_WEIGHT_V8", "DEPTH_OCC_THRESHOLD"]:
        if k in data:
            try:
                state[k] = float(data[k])
            except:
                pass

    return state

def save_state(state: dict, image_path: str = ""):
    data = {
        "W": {k: float(v) for k, v in state["W"].items()},
        "OCC_MODE": state.get("occ_mode", "v8"),
        "OCCLUSION_STRENGTH_V7": float(state.get("OCCLUSION_STRENGTH_V7", 0.65)),
        "OCCLUSION_WEIGHT_V8": float(state.get("OCCLUSION_WEIGHT_V8", 0.55)),
        "DEPTH_OCC_THRESHOLD": float(state.get("DEPTH_OCC_THRESHOLD", 0.06)),
        "meta": {
            "saved_at": time.time(),
            "image": image_path,
        }
    }
    with open(WEIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def apply_feedback(state: dict, meta: dict, fb: str):
    """
    meta: spot meta (light_eff, occ, path, wall, stab)
    fb: "like" | "dislike"
    """
    W = state["W"]
    occ_mode = state.get("occ_mode", "v8")

    if fb == "dislike":
        if meta["path"] > 0.30:
            W["PATH"] += LR["PATH"]
        if meta["occ"] > 0.20:
            if occ_mode == "v7":
                state["OCCLUSION_STRENGTH_V7"] = min(1.2, state["OCCLUSION_STRENGTH_V7"] + LR["OCC"])
            else:
                state["OCCLUSION_WEIGHT_V8"] = min(1.2, state["OCCLUSION_WEIGHT_V8"] + LR["OCC"])
        if meta["wall"] < 0.30:
            W["WALL"] += LR["WALL"]
        if meta["light_eff"] < 0.95:
            W["LIGHT"] += LR["LIGHT"]
        if meta["stab"] < 0.30:
            W["STAB"] += LR["STAB"]

    elif fb == "like":
        if meta["path"] < 0.20:
            W["PATH"] = max(0.30, W["PATH"] - LR["PATH"] * 0.5)
        if meta["occ"] < 0.15:
            if occ_mode == "v7":
                state["OCCLUSION_STRENGTH_V7"] = max(0.30, state["OCCLUSION_STRENGTH_V7"] - LR["OCC"] * 0.5)
            else:
                state["OCCLUSION_WEIGHT_V8"] = max(0.30, state["OCCLUSION_WEIGHT_V8"] - LR["OCC"] * 0.5)
        if meta["wall"] > 0.50:
            W["WALL"] = max(0.05, W["WALL"] - LR["WALL"] * 0.5)
        if meta["stab"] > 0.50:
            W["STAB"] = max(0.05, W["STAB"] - LR["STAB"] * 0.5)

    # clamp
    import numpy as np
    W["LIGHT"] = float(np.clip(W["LIGHT"], 0.30, 1.20))
    W["WALL"]  = float(np.clip(W["WALL"],  0.05, 0.80))
    W["PATH"]  = float(np.clip(W["PATH"],  0.20, 1.20))
    W["STAB"]  = float(np.clip(W["STAB"],  0.05, 0.60))

    if occ_mode == "v7":
        state["OCCLUSION_STRENGTH_V7"] = float(np.clip(state["OCCLUSION_STRENGTH_V7"], 0.20, 0.65))
    else:
        state["OCCLUSION_WEIGHT_V8"]   = float(np.clip(state["OCCLUSION_WEIGHT_V8"],   0.20, 0.65))
