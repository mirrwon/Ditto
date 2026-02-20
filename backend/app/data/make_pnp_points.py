import json
from pathlib import Path

SRC = Path(r"C:\Users\나\Desktop\71765_json\Training\02.labeling\3D 공간 모델\etc_education_l_002\etc_education_l_002.windows_3d.json")

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))

def save_json(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def pick_face_4(corners_8):
    """
    corners_8: list of [x,y,z] length 8
    규칙:
    - x 값이 두 그룹(면 2개)으로 나뉨 → x가 "더 큰 그룹"을 face로 선택 (일관성)
    - 그 face(4점)에서:
      Top = y 큰쪽
      Bottom = y 작은쪽
      Left = z 작은쪽
      Right = z 큰쪽
    반환: [TL, TR, BR, BL]
    """
    # x 기준으로 두 그룹 분리 (반올림해서 안정화)
    xs = {}
    for p in corners_8:
        xk = round(p[0], 6)
        xs.setdefault(xk, []).append(p)

    if len(xs) != 2:
        # 예외: 혹시 회전/수치 오차로 그룹이 2개가 아니면 그냥 y/z로 상위 4개를 뽑는 fallback
        pts = sorted(corners_8, key=lambda t: (t[0], t[1], t[2]))
        face = pts[:4]
    else:
        # x가 큰 쪽을 선택 (일관)
        x_keys = sorted(xs.keys())
        face = xs[x_keys[-1]]  # x가 큰 면

    # face 4점을 TL/TR/BR/BL 순으로 정렬
    # Top 2개, Bottom 2개
    face_sorted_y = sorted(face, key=lambda p: p[1])
    bottom = face_sorted_y[:2]
    top = face_sorted_y[2:]

    # 각 줄에서 z로 left/right
    bottom = sorted(bottom, key=lambda p: p[2])  # z 작은게 left
    top = sorted(top, key=lambda p: p[2])

    TL = top[0]
    TR = top[1]
    BR = bottom[1]
    BL = bottom[0]
    return [TL, TR, BR, BL]

def main():
    if not SRC.exists():
        raise FileNotFoundError(SRC)

    data = load_json(SRC)
    windows = data.get("windows", [])

    for w in windows:
        c8 = w.get("corners_8")
        if isinstance(c8, list) and len(c8) == 8:
            w["pnp_corners_4"] = pick_face_4(c8)

    out_path = SRC.with_name(SRC.name.replace(".windows_3d.json", ".windows_pnp_4pts.json"))
    save_json(out_path, data)
    print("[OK] wrote:", out_path)
    print("[OK] windows:", len(windows))
    print("[OK] sample pnp_corners_4:", windows[0].get("pnp_corners_4") if windows else None)

if __name__ == "__main__":
    main()
