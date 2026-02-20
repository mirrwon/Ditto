import json
import re
from pathlib import Path

BASE = Path(r"C:\Users\나\Desktop\71765_json")

KEYWORDS = ["asset", "class", "category", "label", "taxonomy", "meta", "dictionary", "mapping"]

def safe_load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None

def score_file(p: Path) -> int:
    s = 0
    name = p.name.lower()
    for k in KEYWORDS:
        if k in name:
            s += 2
    # 파일이 너무 크면(수십 MB) 매핑일 확률은 낮지만 일단 가점
    try:
        size = p.stat().st_size
        if 10_000 < size < 5_000_000:
            s += 1
    except Exception:
        pass
    return s

def find_candidates(base: Path, limit: int = 80):
    files = list(base.rglob("*.json"))
    ranked = sorted(files, key=score_file, reverse=True)
    return ranked[:limit]

def extract_mapping(obj):
    """
    다양한 매핑 포맷을 최대한 흡수:
    - {"assets":[{"id":46,"name":"window",...}, ...]}
    - {"categories":[{"id":46,"name":"..."}]}
    - {"class":[...]}
    - {"46":"window", ...}
    반환: dict[int,str] (id -> label)
    """
    mapping = {}

    if isinstance(obj, dict):
        # case A: { "assets": [ {id, name}, ... ] } 같은 형태
        for key in ["assets", "asset", "categories", "category", "classes", "class", "labels", "label", "items"]:
            v = obj.get(key)
            if isinstance(v, list):
                for it in v:
                    if not isinstance(it, dict):
                        continue
                    _id = it.get("id") or it.get("asset_id") or it.get("class_id") or it.get("category_id")
                    _name = it.get("name") or it.get("label") or it.get("title") or it.get("category_name") or it.get("class_name")
                    if _id is not None and _name:
                        try:
                            mapping[int(_id)] = str(_name)
                        except Exception:
                            pass

        # case B: {"46":"window", ...} 같은 형태
        # (문자열 숫자 키들을 라벨로 보는 패턴)
        numeric_keys = 0
        for k, v in obj.items():
            if isinstance(k, str) and re.fullmatch(r"\d+", k) and isinstance(v, (str, int, float)):
                numeric_keys += 1
                try:
                    mapping[int(k)] = str(v)
                except Exception:
                    pass
        # numeric_keys가 너무 적으면 우연일 수도 있음 -> 그대로 두되 나중에 스코어로 판단

    return mapping

def main():
    if not BASE.exists():
        raise FileNotFoundError(BASE)

    candidates = find_candidates(BASE)

    found = []
    for p in candidates:
        data = safe_load_json(p)
        if data is None:
            continue
        m = extract_mapping(data)
        if len(m) >= 10:  # 최소 10개 이상이면 매핑일 확률 높음
            found.append((p, len(m), m))

    print("=== MAPPING CANDIDATES (top) ===")
    if not found:
        print("No mapping-like json found in top candidates.")
        print("Next step: scan deeper with more candidates or inspect dataset docs folder if exists.")
        return

    found.sort(key=lambda x: x[1], reverse=True)

    # 상위 3개만 출력
    for i, (p, n, m) in enumerate(found[:3], 1):
        print(f"\n[{i}] file: {p}")
        print(f"    mapping_size: {n}")
        # 샘플 15개만 보여줌
        sample = list(m.items())[:15]
        print("    sample:")
        for k, v in sample:
            print(f"      {k}: {v}")

    # 1등 후보를 파일로 저장
    best_path, best_n, best_map = found[0]
    out_path = Path(__file__).parent / "asset_id_mapping.json"
    out_path.write_text(json.dumps(best_map, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] wrote mapping: {out_path}")
    print(f"[OK] best source: {best_path}")

if __name__ == "__main__":
    main()
