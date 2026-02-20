import json
from pathlib import Path

# 1) 네 매핑 파일(이미 생성됨)
MAPPING_PATH = Path(__file__).parent / "asset_id_mapping.json"

# 2) 71765 json 루트 폴더
BASE_71765 = Path(r"C:\Users\나\Desktop\71765_json")

# 3) semantic type 규칙(확정)
# - mapping label 기준으로 window/floor/wall/door 등으로 분류
def semantic_type(label: str) -> str:
    if not label:
        return "unknown"
    s = label.strip().lower()

    # 확정 규칙: 네 매핑 샘플 기반
    if s in ["window"] or "window" in s or "창" in label:
        return "window"
    if s in ["deffloor", "floor"] or "floor" in s or "바닥" in label:
        return "floor"
    if s in ["defwall", "wall"] or "wall" in s or "벽" in label:
        return "wall"
    if s in ["door"] or "door" in s or "문" in label:
        return "door"
    if "ceiling" in s or "ceil" in s or "천장" in label:
        return "ceiling"

    return "furniture_or_object"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))


def save_json(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mapping() -> dict:
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Missing mapping file: {MAPPING_PATH}")
    m = load_json(MAPPING_PATH)

    # mapping 키가 문자열/정수 혼재 가능 → 둘 다 대응되게 정규화
    normalized = {}
    for k, v in m.items():
        try:
            normalized[int(k)] = str(v)
        except Exception:
            # 혹시 이미 int 키면
            if isinstance(k, int):
                normalized[k] = str(v)
    return normalized


def is_3d_model_parsed_file(p: Path) -> bool:
    # 네 폴더 구조 기준: "3D 공간 모델" 쪽 parsed.json만 처리
    s = str(p)
    return p.name.endswith(".parsed.json") and ("3D 공간 모델" in s or "3D" in s)


def enrich_one(parsed_path: Path, mapping: dict) -> Path:
    data = load_json(parsed_path)
    objs = data.get("objects", [])

    # 2D 라벨 parsed는 objects가 비어있을 수 있음 → 그대로 새 파일 만들되,
    # 3D 모델에서만 의미 있게 채워짐
    for o in objs:
        aid = o.get("asset_id")
        if aid is None:
            o["label"] = None
            o["semantic_type"] = "unknown"
            continue

        try:
            aid_int = int(aid)
        except Exception:
            aid_int = None

        label = mapping.get(aid_int) if aid_int is not None else None
        o["label"] = label
        o["semantic_type"] = semantic_type(label or "")

    out_path = parsed_path.with_name(parsed_path.name.replace(".parsed.json", ".parsed_3d_semantic.json"))
    save_json(out_path, data)
    return out_path


def main():
    mapping = load_mapping()

    parsed_files = [p for p in BASE_71765.rglob("*.parsed.json") if is_3d_model_parsed_file(p)]
    if not parsed_files:
        print("[ERR] No 3D-model *.parsed.json found under:", BASE_71765)
        print("      (Hint) Ensure you parsed a JSON under '3D 공간 모델' first.")
        return

    out_files = []
    for p in parsed_files:
        out_files.append(enrich_one(p, mapping))

    print(f"[OK] input parsed files: {len(parsed_files)}")
