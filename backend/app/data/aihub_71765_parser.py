import json
import sys
from pathlib import Path

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))

def save_json(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def parse_71765(src: Path) -> dict:
    root = load_json(src)

    info = root.get("info") or {}
    out_info = {
        "description": info.get("description", "가상 실내 공간 3D 합성 데이터"),
        "version": info.get("version", "1.0.0"),
        "year": info.get("year", 2023),
    }

    ann = root.get("annotations")
    objects = []

    # 핵심: 71765 3D 공간 모델은 root.annotations[*]가 바로 3D OBB를 들고 있음
    if isinstance(ann, list):
        for a in ann:
            if not isinstance(a, dict):
                continue

            # 필수키 확인
            required = ["id", "asset_id", "cx", "cy", "cz", "width", "depth", "height", "rx", "ry", "rz"]
            if any(k not in a for k in required):
                continue

            objects.append({
                "id": str(a["id"]),
                "asset_id": int(a["asset_id"]),
                "box3d": {
                    "cx": float(a["cx"]),
                    "cy": float(a["cy"]),
                    "cz": float(a["cz"]),
                    "width": float(a["width"]),
                    "depth": float(a["depth"]),
                    "height": float(a["height"]),
                    "rx": float(a["rx"]),
                    "ry": float(a["ry"]),
                    "rz": float(a["rz"]),
                }
            })

    return {"info": out_info, "objects": objects}

def main():
    if len(sys.argv) < 2:
        print("usage: python aihub_71765_parser.py <path_to_json>", file=sys.stderr)
        return 2

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"[ERR] FileNotFound: {src}", file=sys.stderr)
        return 2

    parsed = parse_71765(src)

    # stdout
    print(json.dumps(parsed, ensure_ascii=False, indent=2))

    # 파일 저장
    dst = src.with_suffix(".parsed.json")
    save_json(dst, parsed)
    print(f"[OK] wrote: {dst}")
    print(f"[OK] objects: {len(parsed.get('objects', []))}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
