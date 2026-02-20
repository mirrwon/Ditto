import json
from pathlib import Path

SRC = Path(r"C:\Users\나\Desktop\71765_json\Training\02.labeling\3D 공간 모델\etc_education_l_001\etc_education_l_001.json")

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))

TARGET_KEYS = {"asset_id", "cx", "cy", "cz", "width", "depth", "height"}
BOX_KEYS = {"cx", "cy", "cz", "width", "depth", "height", "rx", "ry", "rz"}

def score_dict(d: dict) -> int:
    # dict 안에 3D 박스 관련 키가 얼마나 있는지
    return sum(1 for k in BOX_KEYS if k in d)

def walk(node, path="root", hits=None, limit=30):
    if hits is None:
        hits = []

    if isinstance(node, dict):
        # object 후보: asset_id 포함 + box 키 몇개라도 있으면 히트
        if "asset_id" in node:
            sc = score_dict(node) + (score_dict(node.get("box3d", {})) if isinstance(node.get("box3d"), dict) else 0)
            if sc >= 4:  # 키 4개 이상이면 3D 후보로 간주
                hits.append((path, sc, list(node.keys())[:25]))
                if len(hits) >= limit:
                    return hits

        for k, v in node.items():
            hits = walk(v, f"{path}.{k}", hits, limit)
            if len(hits) >= limit:
                return hits

    elif isinstance(node, list):
        for i, v in enumerate(node[:200]):  # 너무 길면 앞부분만
            hits = walk(v, f"{path}[{i}]", hits, limit)
            if len(hits) >= limit:
                return hits

    return hits

def main():
    if not SRC.exists():
        raise FileNotFoundError(SRC)

    data = load_json(SRC)
    hits = walk(data)

    print("[DBG] file:", SRC)
    print("[DBG] top keys:", list(data.keys())[:50])
    print("[DBG] hits:", len(hits))

    for i, (p, sc, keys) in enumerate(hits[:20], 1):
        print(f"\n[{i}] path={p}")
        print(f"    score={sc}")
        print(f"    keys(sample)={keys}")

if __name__ == "__main__":
    main()
