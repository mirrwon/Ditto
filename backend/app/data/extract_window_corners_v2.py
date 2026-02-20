import json
import math
from pathlib import Path

# 네 semantic 파일 경로로 고정
SRC = Path(r"C:\Users\나\Desktop\71765_json\Training\02.labeling\3D 공간 모델\etc_education_l_001\etc_education_l_001.parsed_3d_semantic.json")

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))

def save_json(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def rot_z(yaw: float):
    c = math.cos(yaw)
    s = math.sin(yaw)
    return [
        [c, -s, 0.0],
        [s,  c, 0.0],
        [0.0, 0.0, 1.0],
    ]

def mat_vec(R, v):
    return [
        R[0][0]*v[0] + R[0][1]*v[1] + R[0][2]*v[2],
        R[1][0]*v[0] + R[1][1]*v[1] + R[1][2]*v[2],
        R[2][0]*v[0] + R[2][1]*v[1] + R[2][2]*v[2],
    ]

def add(a, b):
    return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]

def compute_obb_corners(cx, cy, cz, width, depth, height, rz):
    """
    71765 box3d 가정(지금 데이터 구조 기준):
    - center: (cx, cy, cz)
    - size: width(x축), height(y축), depth(z축)
    - rotation: rz (yaw)만 적용 (현재 데이터에서 rz가 핵심)
    """
    hx = width / 2.0
    hy = height / 2.0
    hz = depth / 2.0

    # 로컬 8코너 (x,y,z)
    local = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                local.append([sx*hx, sy*hy, sz*hz])

    R = rot_z(rz)
    center = [cx, cy, cz]

    corners = []
    for p in local:
        rp = mat_vec(R, p)
        corners.append(add(center, rp))

    return corners

def main():
    if not SRC.exists():
        raise FileNotFoundError(SRC)

    data = load_json(SRC)
    objs = data.get("objects", [])

    windows = []
    for o in objs:
        if not isinstance(o, dict):
            continue
        if o.get("semantic_type") != "window":
            continue

        b = o.get("box3d") or {}
        cx = float(b["cx"]); cy = float(b["cy"]); cz = float(b["cz"])
        w  = float(b["width"]); d = float(b["depth"]); h = float(b["height"])
        rz = float(b["rz"])

        corners8 = compute_obb_corners(cx, cy, cz, w, d, h, rz)

        windows.append({
            "id": o.get("id"),
            "asset_id": o.get("asset_id"),
            "label": o.get("label"),
            "semantic_type": o.get("semantic_type"),
            "center": [cx, cy, cz],
            "size": [w, d, h],
            "rz": rz,
            "corners_8": corners8
        })

    out = {
        "source": str(SRC),
        "window_count": len(windows),
        "windows": windows
    }

    out_path = SRC.with_name(SRC.name.replace(".parsed_3d_semantic.json", ".windows_3d.json"))
    save_json(out_path, out)
    print("[OK] windows:", len(windows))
    print("[OK] wrote:", out_path)

if __name__ == "__main__":
    main()
