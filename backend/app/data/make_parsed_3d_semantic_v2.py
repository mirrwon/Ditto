import json
from pathlib import Path

# 1) 매핑 파일은 app/data 폴더에 있다고 가정
MAPPING_PATH = Path(__file__).parent / "asset_id_mapping.json"

# 2) 71765 루트(여기만 네 환경에 맞게 1번만 고치면 됨)
BASE_71765 = Path(r"C:\Users\나\Desktop\71765_json")  # <- 혹시 다르면 여기만 수정

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))

def save_json(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def load_mapping() -> dict:
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"[ERR] Missing mapping file: {MAPPING_PATH}")
    raw = load_json(MAPPING_PATH)

    normalized = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                normalized[int(k)] = str(v)
            except Exception:
                if isinstance(k, int):
                    normalized[k] = str(v)
    return normalized

def semantic_type(label: str) -> str:
    if not label:
        return "unknown"
    s = label.strip().lower()

    if s == "window" or "window" in s or "창" in label:
        return "window"
    if s in ["deffloor", "floor"] or "floor" in s or "바닥" in label:
        return "floor"
    if s in ["defwall", "wall"] or "wall" in s or "벽" in label:
        return "wall"
    if s == "door" or "door" in s or "문" in label:
        return "door"
    if "ceiling" in s or "ceil" in s or "천장" in label:
        return "ceiling"

    return "furniture_or_object"

def enrich_one(parsed_path: Path, mapping: dict) -> Path:
    data = load_json(parsed_path)
    objs = data.get("objects", [])
    if not isinstance(objs, list):
        objs = []

    for o in objs:
        if not isinstance(o, dict):
            continue
        aid = o.get("asset_id")

        label = None
        try:
            aid_int = int(aid)
            label = mapping.get(aid_int)
        except Exception:
            label = None

        o["label"] = label
        o["semantic_type"] = semantic_type(label or "")

    out_path = parsed_path.with_name(parsed_path.name.replace(".parsed.json", ".parsed_3d_semantic.json"))
    save_json(out_path, data)
    return out_path

def main():
    print("[DBG] BASE_71765 =", BASE_71765)
    print("[DBG] BASE exists =", BASE_71765.exists())
    print("[DBG] MAPPING_PATH =", MAPPING_PATH)
    print("[DBG] MAPPING exists =", MAPPING_PATH.exists())

    if not BASE_71765.exists():
        raise FileNotFoundError(f"[ERR] 71765 root not found: {BASE_71765}")

    mapping = load_mapping()
    print("[DBG] mapping size =", len(mapping))

    parsed_files = list(BASE_71765.rglob("*.parsed.json"))
    print("[DBG] found *.parsed.json =", len(parsed_files))

    if not parsed_files:
        print("[ERR] No *.parsed.json found. 먼저 aihub_71765_parser.py로 parsed.json을 생성해야 함.")
        return

    out_files = []
    for p in parsed_files:
        out_files.append(enrich_one(p, mapping))

    print(f"[OK] wrote semantic files: {len(out_files)}")
    print("[OK] sample outputs:")
    for p in out_files[:10]:
        print(" -", p)

if __name__ == "__main__":
    main()
