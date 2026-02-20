import os

# =========================
# ROOTS
# =========================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(APP_DIR)

# =========================
# SAM
# =========================
MODEL_DIR = os.path.join(APP_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

SAM_CKPT = os.path.join(MODEL_DIR, "sam_vit_b.pth")

# =========================
# DEFAULT IMAGE / UPLOAD
# =========================
DEFAULT_ROOM_IMG = os.path.join(BASE_DIR, "room.jpg")

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =========================
# RESULTS / LOGS / WEIGHTS
# =========================
RESULT_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULT_DIR, exist_ok=True)

RESULT_JSON_LATEST = os.path.join(RESULT_DIR, "result_latest.json")

WEIGHTS_PATH = os.path.join(BASE_DIR, "weights.json")
FAIL_LOG_PATH = os.path.join(BASE_DIR, "failures.jsonl")
FB_LOG_PATH = os.path.join(BASE_DIR, "feedback.jsonl")

# (선택) static mount용
PLANTS_DIR = os.path.join(BASE_DIR, "plants")
os.makedirs(PLANTS_DIR, exist_ok=True)

ASSET_DIR = os.path.join(BASE_DIR, "assets")

# =========================
# DEBUG
# =========================
def debug_print_paths():
    print("\n[CONFIG PATHS]")
    print("  BASE_DIR        =", BASE_DIR)
    print("  APP_DIR         =", APP_DIR)
    print("  MODEL_DIR       =", MODEL_DIR)
    print("  SAM_CKPT        =", SAM_CKPT)
    print("  DEFAULT_ROOM_IMG=", DEFAULT_ROOM_IMG)
    print("  UPLOAD_DIR      =", UPLOAD_DIR)
    print("  RESULT_DIR      =", RESULT_DIR)
    print("  RESULT_JSON     =", RESULT_JSON_LATEST)
    print("  WEIGHTS_PATH    =", WEIGHTS_PATH)
    print("  FAIL_LOG_PATH   =", FAIL_LOG_PATH)
    print("  FB_LOG_PATH     =", FB_LOG_PATH)
    print("  PLANTS_DIR      =", PLANTS_DIR)
    print("  ASSET_DIR       =", ASSET_DIR)
    print("")
