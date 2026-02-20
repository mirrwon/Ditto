import os
import sys
import json
import subprocess
from pathlib import Path

BASE = Path(r"C:\Users\나\Desktop\71765_json")
PARSER = Path(__file__).parent / "aihub_71765_parser.py"  # 같은 폴더에 있다고 가정

PREFERRED_PATH_KEYWORDS = [
    "3D", "3d", "pose", "Pose", "box", "Box", "3차원", "3D 공간", "3D공간", "3D 공간 모델"
]

def looks_like_3d_label(json_path: Path) -> bool:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False

    s = json.dumps(data, ensure_ascii=False)

    # 71765 3D 라벨에서 자주 보이는 키 후보들
    keys = [
        "asset_id", "\"rx\"", "\"ry\"", "\"rz\"",
        "\"cx\"", "\"cy\"", "\"cz\"",
        "width", "depth", "height"
    ]
    hit = sum(1 for k in keys if k in s)
    return hit >= 2

def find_best_json(base: Path) -> Path:
    # Training/Validation/Sublabel 순서 우선
    for sub in ["Training", "Validation", "Sublabel"]:
        root = base / sub
        if not root.exists():
            continue

        all_json = list(root.rglob("*.json"))
        if not all_json:
            continue

        # (A) 경로에 3D 힌트 키워드 포함된 파일 우선
        preferred = []
        for p in all_json:
            p_str = str(p)
            if any(k in p_str for k in PREFERRED_PATH_KEYWORDS):
                preferred.append(p)

        for p in preferred:
            if looks_like_3d_label(p):
                return p

        # (B) 전체 중 내용 검사로 3D 후보 찾기
        for p in all_json:
            if looks_like_3d_label(p):
                return p

    # fallback (디버깅용)
    for p in base.rglob("*.json"):
        return p
    raise FileNotFoundError(f"No json found under: {base}")

def main():
    if not BASE.exists():
        raise FileNotFoundError(BASE)
    if not PARSER.exists():
        raise FileNotFoundError(f"Parser not found: {PARSER}")

    sample_json = find_best_json(BASE)

    print("BASE:", BASE)
    print("PARSER:", PARSER)
    print("SAMPLE_JSON:", sample_json)
    print("EXISTS:", sample_json.exists())
    print("SIZE:", sample_json.stat().st_size, "bytes")

    cmd = [sys.executable, str(PARSER), str(sample_json)]
    print("RUN:", cmd)

    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("\n===== STDOUT =====\n", res.stdout)
    print("\n===== STDERR =====\n", res.stderr)

if __name__ == "__main__":
    main()
