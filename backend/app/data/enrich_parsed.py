import json
from pathlib import Path

MAPPING_PATH = Path(__file__).parent / "asset_id_mapping.json"
# 너가 만든 parsed.json 경로로 바꿔도 되고, 폴더 전체 처리도 가능
TARGET_PARSED = Path(r"C:\Users\나\Desktop\71765_json")

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))

def save_json(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def enrich_one(parsed_path: Path, mapping: dict) -> bool:
    data = load_json(parsed_path)
    objs = data.get("objects", [])
    changed = False

    for o in objs:
        aid = o.get("asset_id")
        if aid is None:
            continue
        label = mapping.get(str(aid)) or mapping.get(int(aid)) if isinstance(aid, int) else mapping.get(aid)
        if label and o.get("label") != label:
            o["label"] = label
            changed = True

    if changed:
        save_json(parsed_path, data)
    return changed

def main():
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Missing mapping: {MAPPING_PATH}")

    mapping = load_json(MAPPING_PATH)

    parsed_files = list(TARGET_PARSED.rglob("*.parsed.json"))
    if not parsed_files:
        print("No *.parsed.json found under:", TARGET_PARSED)
        return

    n_changed = 0
    for p in parsed_files:
        if enrich_one(p, mapping):
            n_changed += 1

    print(f"[OK] parsed files: {len(parsed_files)}")
    print(f"[OK] enriched: {n_changed}")

if __name__ == "__main__":
    main()
