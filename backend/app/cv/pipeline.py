import os, json, time, glob
import cv2
import numpy as np
import torch
import re
import shutil
from pathlib import Path

from app.config import (
    BASE_DIR, RESULT_DIR, RESULT_JSON_LATEST, FAIL_LOG_PATH, FB_LOG_PATH, WEIGHTS_PATH,
    debug_print_paths
)

from app.cv.utils import (
    floor_core,
    candidates_from_mask,
    distance_to_boundary,
    depth_stability,
    occ_v8_depth,
    classify_surface_by_depth,
    cluster_and_pick,
    to_jsonable,
    daily_light_area,
)

from .sam.sam_vit import segment_floor, get_floor_center
from .geometry.window_detect import detect_window_candidate, base_dir
from .viz import draw_debug
from .depth.depth_midas import get_depth

from app.cv.cv_config import (
    CAND_STEP, MAX_N, CLUSTER_DIST,
    SURFACE_PENALTY, SURFACE_PENALTY_ONLY_IF_HAS_FLOOR,
    WINDOW_SAMPLES, RAY_SAMPLES,
    DEPTH_OCC_THRESHOLD, OCC_MODE, OCCLUSION_WEIGHT_V8, OCCLUSION_STRENGTH_V7,
    W, MIN_WALL, MIN_STAB, PLANT_PENALTY,
    MIN_ORIGIN_DIST_PX, MIN_WALL_FOR_BEST, BEST_STAB_BONUS,
)

from .pnp_pose import solve_pnp_from_4pts, window_normal_world
from .window_mask import extract_window_corners_edge, extract_window_corners_hough
from app.cv.camera_intrinsics import make_K_from_fov

print("[PIPELINE FILE]", __file__)

DATASET_71765_ROOT = os.environ.get(
    "DATASET_71765_ROOT",
    r"C:\Users\나\Desktop\71765_json\71765_json"
)

def _peek_label(scene_dir: str) -> str:
    # 폴더 안 json 하나 집어서 label 비슷한 키 찾아보기
    js = glob.glob(os.path.join(scene_dir, "*.json"))
    if not js:
        return ""
    try:
        with open(js[0], "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return ""

    # 흔한 키 후보들
    for k in ("room_type","space_type","category","scene_type","label","place","name"):
        v = d.get(k) if isinstance(d, dict) else None
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            for kk in ("label","name","type"):
                vv = v.get(kk)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
    return ""

def list_71765_scenes() -> list:
    """
    71765 3D 실내데이터 폴더에서 scene_id 목록을 전부 수집한다.

    ✅ 루트: C:\\Users\\나\\Desktop\\71765_json\\71765_json
    - 내부에 'Training/02.labeling/3D 공간 모델/<scene_id>/<scene_id>.json'
      같은 구조가 있을 수 있음
    - 어떤 하위 폴더 구조든 상관없이:
      "<scene_id>.json" 파일을 찾고,
      파일명에서 scene_id를 추출해서 반환한다.

    반환: ["residence_house_1_s_001", "etc_education_l_002", ...]
    """

    # ROOT = r"C:\Users\나\Desktop\71765_json\71765_json\Training\02.labeling\3D 공간 모델"
    ROOT = r"C:\Users\201\Desktop\71765_json\71765_json\Training\02.labeling\3D 공간 모델"

    if not os.path.isdir(ROOT):
        print("[list_71765_scenes] ROOT not found:", ROOT)
        return []

    # ✅ 모든 json 파일을 수집(너무 많으면 시간이 걸릴 수 있음)
    # - 일반적으로 scene json은 "<scene_id>.json" 형태
    # - assets 같은 대용량 json이라도 확장자는 .json이므로 일단 다 잡고 필터링
    all_jsons = glob.glob(os.path.join(ROOT, "**", "*.json"), recursive=True)

    scene_ids = set()

    for p in all_jsons:
        base = os.path.basename(p)

        # 1) 파일명이 scene_id.json 형태면 scene_id 후보
        if base.lower().endswith(".json"):
            sid = base[:-5]  # remove ".json"
            if not sid:
                continue

            # 2) 너무 일반적인 파일명/라벨/메타 파일은 제외하고 싶으면 여기서 필터
            #    (프로젝트 상황에 따라 조정)
            # 예: windows_pnp_4pts 같은 보조 json 제외
            if sid.endswith(".windows_pnp_4pts"):
                continue
            if sid.endswith("_windows_pnp_4pts"):
                continue
            if "windows_pnp" in sid:
                continue

            # 네가 원하는 건 원룸/투룸 위주라면 residence 계열만 추려도 됨(옵션)
            if not sid.startswith("residence_"):
                continue

            scene_ids.add(sid)

    out = sorted(scene_ids)
    print("[list_71765_scenes] found scenes =", len(out))
    if len(out) > 0:
        print("[list_71765_scenes] sample =", out[:10])

    return out


def build_windows_pnp_json_path(scene_id: str) -> str | None:
    """
    scene_id -> .../3D 공간 모델/<scene_id>/<scene_id>.windows_pnp_4pts.json
    """
    if not re.fullmatch(r"etc_education_l_\d{3}", str(scene_id)):
        return None
    p = Path(DATASET_71765_ROOT) / "Training" / "02.labeling" / "3D 공간 모델" / scene_id / f"{scene_id}.windows_pnp_4pts.json"
    return str(p) if p.exists() else None

# =========================================================
# Helpers (2D ordering / quad validation)
# =========================================================
def _find_pnp_json_by_uploaded_filename(image_path: str) -> str | None:
    """
    uploads/room2.jpg 같은 업로드 이미지에서 scene_id를 못 찾을 때:
    - 파일 stem(room2)로 71765 3D 폴더 내부를 탐색해서
      <scene>/<stem>.jpg 가 있는 scene을 찾고
      그 scene의 <scene>.windows_pnp_4pts.json 경로를 반환
    """
    stem = Path(image_path).stem  # room2
    root = Path(DATASET_71765_ROOT)

    base_3d = root / "Training" / "02.labeling" / "3D 공간 모델"
    if not base_3d.exists():
        return None

    # etc_education_l_XXX 폴더들 순회
    for scene_dir in base_3d.glob("etc_education_l_*"):
        if not scene_dir.is_dir():
            continue
        # scene_dir/room2.jpg 존재하면 매칭
        cand_img = scene_dir / f"{stem}.jpg"
        if cand_img.exists():
            scene_id = scene_dir.name
            json_path = scene_dir / f"{scene_id}.windows_pnp_4pts.json"
            if json_path.exists():
                return str(json_path)

    return None

def order_2d_tl_tr_br_bl(pts4):
    """
    pts4: (4,2)
    return: (4,2) in TL,TR,BR,BL
    """
    p = np.array(pts4, dtype=np.float32).reshape(4, 2)
    s = p.sum(axis=1)           # x+y
    d = (p[:, 0] - p[:, 1])     # x-y

    tl = p[np.argmin(s)]
    br = p[np.argmax(s)]
    tr = p[np.argmax(d)]
    bl = p[np.argmin(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def quad_is_valid(pts4, min_area=50.0):
    """
    - area too small -> fail
    - self-intersection (bow-tie) -> fail
    """
    p = np.array(pts4, dtype=np.float32).reshape(4, 2)

    # polygon area (shoelace)
    x = p[:, 0]
    y = p[:, 1]
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    if area < float(min_area):
        return False, f"area too small: {area:.2f}"

    def _ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    def _intersect(a, b, c, d):
        return (_ccw(a, c, d) != _ccw(b, c, d)) and (_ccw(a, b, c) != _ccw(a, b, d))

    TL, TR, BR, BL = p
    if _intersect(TL, TR, BR, BL) or _intersect(TR, BR, BL, TL):
        return False, "self-intersection"

    return True, "ok"


def _bbox_to_corners4(win_bbox):
    x, y, w, h = [float(v) for v in win_bbox]
    return np.array([
        [x,     y],
        [x + w, y],
        [x + w, y + h],
        [x,     y + h],
    ], dtype=np.float32)


def _is_bbox_like(c4, bbox4, eps=3.0) -> bool:
    if c4 is None:
        return False
    c4 = np.array(c4, dtype=np.float32).reshape(4, 2)
    bbox4 = np.array(bbox4, dtype=np.float32).reshape(4, 2)
    for p in c4:
        d = np.min(np.linalg.norm(bbox4 - p[None, :], axis=1))
        if d > eps:
            return False
    return True


# =========================================================
# Helpers (71765 A 방식 로더: scene -> windows_pnp_4pts.json)
# =========================================================
def _find_scene_dir_from_image(image_path: str) -> Path | None:
    """
    image_path에서 etc_education_l_XXX scene 폴더를 최대한 관대하게 찾아 반환.
    - 폴더명으로 못 찾으면, 전체 경로 문자열에서 패턴으로 scene_id를 추출해서
      2D/3D 베이스 경로를 재구성할 수 있게 보조 정보를 남김.
    """
    p = Path(image_path)

    # 1) 부모 경로를 올라가며 폴더명으로 찾기 (기존 방식 + 강화)
    for parent in [p] + list(p.parents):
        name = parent.name
        if name.startswith("etc_education_l_") and re.fullmatch(r"etc_education_l_\d{3}", name):
            return parent

    # 2) 경로 문자열 전체에서 패턴으로 scene_id 찾기 (폴더명이 중간에 누락/변형된 케이스 대비)
    m = re.search(r"(etc_education_l_\d{3})", str(p))
    if m:
        # 여기서는 "scene 폴더 Path"를 직접 만들 수 없으니,
        # 호출부에서 string 기반으로 2D->3D 변환할 수 있게
        # 임시로 해당 문자열을 name으로 갖는 가상 Path를 반환하지 않고,
        # None 반환하되, 호출부에서 m.group(1)로 처리하는 방식이 안전.
        return Path(m.group(1))  # 주의: 실제 경로 아님(식별자 용도)

    return None

def load_windows_pnp_4pts_from_71765(
    image_path: str,
    override_json_path: str | None = None,
    scene_id: str | None = None
):
    """
    image_path가 2D/3D 어디를 가리켜도,
    scene_id 기반으로 .../3D 공간 모델/<scene_id>/<scene_id>.windows_pnp_4pts.json 을 찾아 로드.
    override_json_path가 있으면 그걸 최우선으로 사용.
    """
    dbg = {"ok": False, "reason": "", "json_path": None, "picked": None, "num_windows": 0}

    # --------------------------
    # 0) override json path 우선
    # --------------------------
    if override_json_path:
        json_path = Path(override_json_path)
        dbg["json_path"] = str(json_path)

        if not json_path.exists():
            dbg["reason"] = "override_json_not_found"
            return None, dbg

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            dbg["reason"] = f"json_load_failed: {e}"
            return None, dbg

        # 아래 windows 파싱/선택 로직으로 진행
        windows = None
        if isinstance(data, dict) and isinstance(data.get("windows"), list):
            windows = data["windows"]
        elif isinstance(data, list):
            windows = data
        else:
            dbg["reason"] = "unexpected_json_schema"
            return None, dbg

        dbg["num_windows"] = int(len(windows))
        if not windows:
            dbg["reason"] = "windows_list_empty"
            return None, dbg

        candidates = []
        for w in windows:
            c4 = w.get("pnp_corners_4")
            if not (isinstance(c4, list) and len(c4) == 4):
                continue

            score = 0.0
            if isinstance(w.get("size"), list) and len(w["size"]) >= 3:
                try:
                    score = float(w["size"][1]) * float(w["size"][2])
                except Exception:
                    score = 0.0
            candidates.append((score, w))

        if not candidates:
            dbg["reason"] = "no_valid_pnp_corners_4"
            return None, dbg

        candidates.sort(key=lambda x: x[0], reverse=True)
        picked = candidates[0][1]
        c4 = picked["pnp_corners_4"]  # (4,3)

        dbg["ok"] = True
        dbg["picked"] = {
            "id": picked.get("id"),
            "asset_id": picked.get("asset_id"),
            "label": picked.get("label"),
            "semantic_type": picked.get("semantic_type"),
            "size": picked.get("size"),
            "score": candidates[0][0],
        }

        # ✅ 여기: windows(list)가 아니라 "picked 4pts"를 반환해야 타입이 안 꼬임
        return c4, dbg

    # --------------------------
    # 1) scene_id 인자 우선 적용
    # --------------------------
    if scene_id:
        jp = build_windows_pnp_json_path(scene_id)
        if jp:
            # scene_id로 json_path 강제 지정해서 override처럼 처리
            return load_windows_pnp_4pts_from_71765(image_path, override_json_path=jp)

    # --------------------------
    # 1) scene_id 찾기
    # --------------------------
    scene_dir = _find_scene_dir_from_image(image_path)

    print("[PNP3D][PATH] image_path =", image_path)
    print("[PNP3D][PATH] scene_dir =", scene_dir)

    scene_id = None
    if scene_dir is not None and re.fullmatch(r"etc_education_l_\d{3}", scene_dir.name):
        scene_id = scene_dir.name
    else:
        m = re.search(r"(etc_education_l_\d{3})", str(image_path))
        if m:
            scene_id = m.group(1)

    if scene_id is None:
        auto_json = _find_pnp_json_by_uploaded_filename(image_path)
        if auto_json:
            return load_windows_pnp_4pts_from_71765(image_path, override_json_path=auto_json)

        dbg["reason"] = "scene_required"
        dbg["image_path"] = str(image_path)
        dbg["scenes"] = list_71765_scenes()[:200]  # 너무 길면 제한
        return None, dbg

    # --------------------------
    # 2) 02.labeling 기준으로 3D 경로 만들기
    #    (2D로 들어오든 3D로 들어오든 둘 다 처리)
    # --------------------------
    p = Path(image_path)
    parts = list(p.parts)

    try:
        idx = parts.index("02.labeling")
    except ValueError:
        dbg["reason"] = "cannot_locate_02.labeling_in_path"
        dbg["image_path"] = str(image_path)
        return None, dbg

    folder = parts[idx + 1] if (idx + 1) < len(parts) else None

    if folder == "2D 공간 이미지":
        parts[idx + 1] = "3D 공간 모델"
    elif folder == "3D 공간 모델":
        # 이미 3D면 그대로
        pass
    else:
        dbg["reason"] = f"unexpected_folder_after_02.labeling: {folder}"
        dbg["image_path"] = str(image_path)
        return None, dbg

    scene_dir_3d = Path(*parts[: idx + 2]) / scene_id
    json_path = scene_dir_3d / f"{scene_id}.windows_pnp_4pts.json"

    dbg["json_path"] = str(json_path)
    if not json_path.exists():
        dbg["reason"] = "windows_pnp_4pts_json_not_found"
        return None, dbg

    # --------------------------
    # 3) JSON 로드 + window 선택
    # --------------------------
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        dbg["reason"] = f"json_load_failed: {e}"
        return None, dbg

    windows = None
    if isinstance(data, dict) and isinstance(data.get("windows"), list):
        windows = data["windows"]
    elif isinstance(data, list):
        windows = data
    else:
        dbg["reason"] = "unexpected_json_schema"
        return None, dbg

    dbg["num_windows"] = int(len(windows))
    if not windows:
        dbg["reason"] = "windows_list_empty"
        return None, dbg

    candidates = []
    for w in windows:
        c4 = w.get("pnp_corners_4")
        if not (isinstance(c4, list) and len(c4) == 4):
            continue

        score = 0.0
        if isinstance(w.get("size"), list) and len(w["size"]) >= 3:
            try:
                score = float(w["size"][1]) * float(w["size"][2])
            except Exception:
                score = 0.0

        candidates.append((score, w))

    if not candidates:
        dbg["reason"] = "no_valid_pnp_corners_4"
        return None, dbg

    candidates.sort(key=lambda x: x[0], reverse=True)
    picked = candidates[0][1]
    c4 = picked["pnp_corners_4"]

    dbg["ok"] = True
    dbg["picked"] = {
        "id": picked.get("id"),
        "asset_id": picked.get("asset_id"),
        "label": picked.get("label"),
        "semantic_type": picked.get("semantic_type"),
        "size": picked.get("size"),
        "score": candidates[0][0],
    }
    return c4, dbg



# =========================================================
# Helpers (3D ordering + reprojection error)
# =========================================================
def order_3d_tl_tr_br_bl(c4_3d):
    """
    3D 4pts를 해당 평면 좌표계로 투영한 뒤 TL/TR/BR/BL로 정렬.
    """
    P = np.array(c4_3d, dtype=np.float32).reshape(4, 3)

    c = P.mean(axis=0)
    v1 = P[1] - P[0]
    v2 = P[3] - P[0]

    u = v1 / (np.linalg.norm(v1) + 1e-6)
    n = np.cross(v1, v2)
    n = n / (np.linalg.norm(n) + 1e-6)
    v = np.cross(n, u)
    v = v / (np.linalg.norm(v) + 1e-6)

    uv = np.stack([np.dot(P - c, u), np.dot(P - c, v)], axis=1)  # (4,2)

    uv_ord = order_2d_tl_tr_br_bl(uv)

    out = []
    used = set()
    for q in uv_ord:
        d = np.linalg.norm(uv - q[None, :], axis=1)
        for idx in np.argsort(d):
            if int(idx) not in used:
                used.add(int(idx))
                out.append(P[int(idx)])
                break

    return np.array(out, dtype=np.float32)  # (4,3)


def reproj_error(obj3d, img2d, rvec, tvec, K, dist=None):
    obj3d = np.array(obj3d, dtype=np.float32).reshape(-1, 3)
    img2d = np.array(img2d, dtype=np.float32).reshape(-1, 2)
    K = np.array(K, dtype=np.float32).reshape(3, 3)
    if dist is None:
        dist = np.zeros((4, 1), dtype=np.float32)

    proj, _ = cv2.projectPoints(obj3d, rvec, tvec, K, dist)
    proj = proj.reshape(-1, 2)
    err = np.linalg.norm(proj - img2d, axis=1)
    return float(np.mean(err))


# =========================================================
# Main
# =========================================================
def run_pipeline(
    image_path: str,
    user_opts: dict | None = None,
    max_n: int | None = None,
    debug_viz: bool = False,
    save_outputs: bool = True,
):
    debug_print_paths()
    os.makedirs(RESULT_DIR, exist_ok=True)

    print("[PIPELINE][RUN] ts_ms =", int(time.time() * 1000))
    print("[PIPELINE][RUN] file  =", __file__)

    # === TEMP TEST: force dataset path ===
    def imread_unicode(path: str):
        try:
            data = np.fromfile(path, dtype=np.uint8)
            if data.size == 0:
                return None
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    img = imread_unicode(image_path)
    if img is None:
        # 폴백으로 cv2.imread도 한 번 시도
        img = cv2.imread(image_path)

    if img is None:
        raise RuntimeError(f"image read failed: {image_path}")

    H, Wimg = img.shape[:2]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # =========================
    # FLOOR (SAM)
    # =========================
    floor_mask_255, _ = segment_floor(img)
    if floor_mask_255 is None:
        raise RuntimeError("floor segmentation failed (SAM returned None)")

    floor = (floor_mask_255 > 0).astype(np.uint8)
    ratio = float(np.sum(floor > 0)) / float(H * Wimg)
    print(f"[FLOOR] area ratio = {ratio:.3f}")
    if ratio < 0.08:
        raise RuntimeError("Floor mask too small -> SAM floor segmentation fail")

    core = floor_core(floor, 19)
    if core.sum() < 500:
        core = floor

    # =========================
    # WINDOW DETECT + REFINE
    # =========================
    win = detect_window_candidate(img, floor, prefer="right", debug=debug_viz)

    window_info = None
    corners4_edge = None
    corners4_h = None

    if win is not None:
        bbox4 = _bbox_to_corners4(win)

        # 1) EDGE refine
        corners4_edge = extract_window_corners_edge(img, win, debug_dir=RESULT_DIR, tag="window")
        corners4 = corners4_edge
        source = "edge"

        # edge가 bbox랑 거의 같으면 실패로 보고 hough 시도
        if corners4 is None or _is_bbox_like(corners4, bbox4, eps=3.0):
            print("[WIN] edge failed or bbox-like -> try hough")
            corners4 = None
            source = "edge_looks_like_bbox"

            corners4_h = extract_window_corners_hough(img, win, debug_dir=RESULT_DIR, tag="window")
            if corners4_h is not None:
                corners4 = corners4_h
                source = "hough"

        # 3) fallback
        if corners4 is None:
            corners4 = bbox4
            source = "bbox_fallback"


        c4 = order_2d_tl_tr_br_bl(np.array(corners4, dtype=np.float32).reshape(4, 2))
        ok, msg = quad_is_valid(c4, min_area=80.0)
        if not ok:
            print("[WIN][WARN] invalid quad:", msg, "-> fallback bbox corners")
            c4 = order_2d_tl_tr_br_bl(bbox4)
            source = (source + "+fallback_bbox").strip("+")

        print("[WIN][BBOX4]   =", bbox4.tolist())
        print("[WIN][EDGE4]   =",
              None if corners4_edge is None else np.array(corners4_edge, dtype=np.float32).reshape(4, 2).tolist())
        print("[WIN][HOUGH4]  =",
              None if corners4_h is None else np.array(corners4_h, dtype=np.float32).reshape(4, 2).tolist())
        print("[WIN][FINAL4]  =", c4.tolist())
        print("[WIN][DIFF] bbox-final L2 mean =",
              float(np.mean(np.linalg.norm(bbox4.astype(np.float32) - np.array(c4, dtype=np.float32), axis=1))))

        x, y, w, h = [int(v) for v in win]
        window_info = {
            "bbox_xywh": [x, y, w, h],
            "corners_4": c4.tolist(),           # TL_TR_BR_BL 확정
            "source": source,
            "pnp_order": "TL_TR_BR_BL",
            "valid_quad": True,
            "valid_msg": "ok" if ok else "fallback_bbox",
        }

        print("[WIN] win bbox:", win)
        print("[WIN] edge corners:", None if corners4_edge is None else np.array(corners4_edge).reshape(4, 2))
        print("[WIN] hough corners:", None if corners4_h is None else np.array(corners4_h).reshape(4, 2))
        print("[WIN] final source:", source)
        print("[WIN][FINAL] source =", window_info["source"])

    # =========================
    # VIZ WINDOWS CACHE (GLOBAL)
    # =========================
    windows_for_viz = []
    if isinstance(window_info, dict) and window_info.get("corners_4"):
        windows_for_viz.append({
            "corners_4": window_info["corners_4"],
            "bbox_xywh": window_info.get("bbox_xywh"),
            "source": window_info.get("source"),
        })

    # =========================
    # LIGHT ORIGIN / DIR
    # =========================
    try:
        fc = get_floor_center(core)
        floor_c = np.array([float(fc[0]), float(fc[1])], dtype=np.float32)
    except Exception:
        ys, xs = np.where(core > 0)
        if len(xs) > 0:
            floor_c = np.array([float(np.mean(xs)), float(np.mean(ys))], dtype=np.float32)
        else:
            floor_c = np.array([Wimg * 0.5, H * 0.8], dtype=np.float32)

    if win is not None:
        x, y, ww, hh = win
        origin = np.array([x + ww * 0.5, y + hh * 0.85], dtype=np.float32)
        base_dir_vec = base_dir(origin, floor_c)
    else:
        origin = np.array([Wimg * 0.8, H * 0.3], dtype=np.float32)
        base_dir_vec = np.array([0.0, 1.0], np.float32)

    # =========================
    # DEPTH / STAB
    # =========================
    depth = get_depth(img, device)
    if depth is None:
        depth = np.zeros((H, Wimg), np.float32)
        stab_raw = np.ones((H, Wimg), np.float32)
        depth_ok = False
    else:
        stab_raw = depth_stability(depth)
        depth_ok = True

    stab = stab_raw * (core > 0).astype(np.float32)
    dist_wall = distance_to_boundary(core)

    pts = candidates_from_mask(core, step=CAND_STEP)
    scored = []
    MARGIN = 12

    if depth_ok:
        floor_depth = depth[core > 0]
        if floor_depth.size > 0:
            floor_d_p20 = float(np.percentile(floor_depth, 20))
            floor_d_p80 = float(np.percentile(floor_depth, 80))
        else:
            floor_d_p20, floor_d_p80 = 0.0, 1.0
    else:
        floor_d_p20, floor_d_p80 = 0.0, 1.0

    light_map = np.zeros((H, Wimg), np.float32)

    for (x, y) in pts:
        if x < MARGIN or x >= Wimg - MARGIN or y < MARGIN or y >= H - MARGIN:
            continue

        times, total = daily_light_area((x, y), origin, base_dir_vec, img)

        od = float(np.hypot(x - float(origin[0]), y - float(origin[1])))
        if od < MIN_ORIGIN_DIST_PX:
            continue

        s_wall = float(dist_wall[y, x])
        s_stab = float(stab[y, x])

        if s_wall < MIN_WALL:
            continue
        if s_stab < MIN_STAB:
            continue

        occ = 0.0 if not depth_ok else occ_v8_depth((int(origin[0]), int(origin[1])), (x, y), depth, core)

        light_eff = total * (0.65 + 0.35 * s_stab) * (1.0 - OCCLUSION_WEIGHT_V8 * occ)
        dval = float(depth[y, x]) if depth_ok else 0.0
        surface = classify_surface_by_depth(dval, floor_d_p20, floor_d_p80)

        if light_eff > 0:
            light_map[y, x] = max(light_map[y, x], float(light_eff))

        raw_score = (
            W["LIGHT"] * float(light_eff) +
            W["WALL"]  * s_wall +
            W["STAB"]  * s_stab
        )

        meta = {
            "pt": (int(x), int(y)),
            "times": times,
            "light_eff": float(light_eff),
            "occ": float(occ),
            "wall": float(s_wall),
            "stab": float(s_stab),
            "depth": float(dval),
            "surface": surface,
            "raw_score": float(raw_score),
            "surface_penalty": 0.0,
            "final_score": float(raw_score),
        }

        scored.append((float(raw_score), (int(x), int(y)), meta))

    # =========================
    # surface penalty
    # =========================
    has_floor_candidate = any(m.get("surface") == "floor" for (_, _, m) in scored)

    scored2 = []
    for (raw_s, pt, meta) in scored:
        surface = meta.get("surface", "floor")
        apply_surface_penalty = (surface == "other")
        if SURFACE_PENALTY_ONLY_IF_HAS_FLOOR:
            apply_surface_penalty = apply_surface_penalty and has_floor_candidate

        surface_pen = float(SURFACE_PENALTY) if apply_surface_penalty else 0.0
        final_s = float(raw_s) - surface_pen

        meta["surface_penalty"] = float(surface_pen)
        meta["final_score"] = float(final_s)
        scored2.append((float(final_s), pt, meta))

    scored = scored2

    if light_map.max() > 0:
        light_map = cv2.GaussianBlur(light_map, (0, 0), 7)

    scored.sort(key=lambda v: v[0], reverse=True)

    use_max = int(max_n) if (max_n is not None) else MAX_N
    chosen = cluster_and_pick(scored, cluster_dist=CLUSTER_DIST, max_total=use_max)
    if not chosen:
        raise RuntimeError("No spots chosen. Try lowering thresholds.")

    # =========================
    # light level + bias
    # =========================
    chosen_light = [float(meta.get("light_eff", 0.0)) for (_, _, meta) in chosen]
    if len(chosen_light) >= 3:
        p20 = float(np.percentile(chosen_light, 20))
        p80 = float(np.percentile(chosen_light, 80))
    else:
        p20, p80 = 0.0, 1e9

    def light_level(le: float) -> str:
        if le >= p80:
            return "bright"
        if le <= p20:
            return "dim"
        return "medium"

    def light_bias(times: dict) -> str:
        if not isinstance(times, dict) or not times:
            return "unknown"
        k = max(times, key=lambda kk: float(times.get(kk, 0.0)))
        return str(k)

    # =========================
    # best spot reselect
    best_idx = 0
    best_val = -1e9
    for i, (s, pt, meta) in enumerate(chosen):
        wall = float(meta.get("wall", 0.0))
        stabv = float(meta.get("stab", 0.0))
        if wall < MIN_WALL_FOR_BEST:
            continue
        val = float(s) + BEST_STAB_BONUS * stabv + 0.05 * wall
        if val > best_val:
            best_val = val
            best_idx = i

    if best_idx != 0:
        chosen[0], chosen[best_idx] = chosen[best_idx], chosen[0]

    packed = []
    for idx, (s, pt, meta) in enumerate(chosen, start=1):
        le = float(meta.get("light_eff", 0.0))
        times = meta.get("times", {}) or {}
        y_norm = pt[1] / float(H)
        stabv = float(meta.get("stab", 0.0))
        lvl = light_level(le)
        surf = meta.get("surface", "floor")

        if surf == "floor" and lvl in ("bright", "medium"):
            spot_usage = "floor_large"
        elif surf != "floor" and stabv > 0.55 and 0.35 < y_norm < 0.75:
            spot_usage = "table_small"
        elif lvl == "dim":
            spot_usage = "low_light"
        else:
            spot_usage = "avoid"

        packed.append({
            "rank": idx,
            "score": float(s),
            "raw_score": float(meta.get("raw_score", s)),
            "surface_penalty": float(meta.get("surface_penalty", 0.0)),
            "final_score": float(meta.get("final_score", s)),
            "pt": [int(pt[0]), int(pt[1])],
            "surface": surf,
            "features": {
                "light_eff": le,
                "occ": float(meta["occ"]),
                "wall": float(meta["wall"]),
                "stab": stabv,
                "times": times,
            },
            "light_profile": {
                "total": le,
                "times": times,
                "bias": light_bias(times),
                "level": lvl,
            },
            "spot_usage": spot_usage,
            "top_plants": []
        })

    def _fmt_arr(a):
        try:
            a = np.asarray(a)
            return f"shape={a.shape} dtype={a.dtype} min={a.min():.2f} max={a.max():.2f} first={a.reshape(-1, a.shape[-1])[:4].tolist()}"
        except Exception as e:
            return f"(format_failed) {type(a)} {e}"

    def _ensure_4x2(corners, name="corners"):
        a = np.asarray(corners, dtype=np.float32)
        if a.shape == (4, 2):
            return a
        if a.size == 8:
            return a.reshape(4, 2)
        raise ValueError(f"{name} invalid shape: {a.shape}, value={corners}")

    # =========================
    # PNP (A 방식): scene windows_pnp_4pts.json
    # - uploads 이미지도 자동 매칭
    # - window 후보 전체 + fov sweep -> reproj error 최소 조합 선택
    # =========================
    scene_result = {"ok": True, "reason": "", "scenes": []}

    pnp_result = None

    def _pack_pnp_success(K_use, rvec_use, tvec_use, R_use, reproj_err_px, picked_window, pnp3d_dbg, used_fov):
        n = window_normal_world(R_use, face_axis="z")
        return {
            "K": K_use.tolist(),
            "rvec": [float(x) for x in rvec_use.reshape(-1)],
            "tvec": [float(x) for x in tvec_use.reshape(-1)],
            "window_normal": [float(x) for x in n.reshape(-1)],
            "reproj_err_px": float(reproj_err_px),
            "used_fov": float(used_fov),
            "picked_window": picked_window,
            "dbg_3d": pnp3d_dbg,
            "note": "PnP(A): choose best window + best fov by reprojection error",
        }

    try:
        if not (isinstance(window_info, dict) and window_info.get("corners_4")):
            pnp_result = {"error": "window_info.corners_4 missing"}
        else:
            img_corners_2d = np.array(window_info["corners_4"], dtype=np.float32).reshape(4, 2)  # TL,TR,BR,BL

            # =========================
            # PNP PRECHECK (2D corners sanity)
            # =========================
            print("\n[PNP_PRECHECK] -----------------------------")
            print("[PNP_PRECHECK] img.shape(H,W,C) =", getattr(img, "shape", None))
            print("[PNP_PRECHECK] win bbox =", win)
            print("[PNP_PRECHECK] window_info['corners_4'] raw =", window_info.get("corners_4", None))
            print("[PNP_PRECHECK] window_info['corners_4'] fmt =", _fmt_arr(window_info.get("corners_4", None)))

            # ✅ 여기서 img_corners_2d는 이미 위에서 정의됨
            img_corners_2d = _ensure_4x2(img_corners_2d, "img_corners_2d")
            w_c4 = _ensure_4x2(window_info.get("corners_4", None), "window_info['corners_4']")

            print("[PNP_PRECHECK] img_corners_2d =", img_corners_2d.tolist())
            print("[PNP_PRECHECK] window_info.corners_4 =", w_c4.tolist())
            print("[PNP_PRECHECK] same_as_window_info =", bool(np.allclose(img_corners_2d, w_c4)))
            print("[PNP_PRECHECK] --------------------------------\n")


            # 1) 3D json 찾기 (override -> 자동)
            override_json = None
            if isinstance(user_opts, dict):
                override_json = user_opts.get("pnp_3d_json_path")

            scene_id_opt = None
            if isinstance(user_opts, dict):
                scene_id_opt = user_opts.get("scene_id")

            obj_corners_3d, pnp3d_dbg = load_windows_pnp_4pts_from_71765(
                image_path,
                override_json_path=override_json,
                scene_id=scene_id_opt,
            )
            print("[PNP3D]", pnp3d_dbg)

            # ✅ scene_required를 PNP와 분리해서 out["scene"]로 올림
            if isinstance(pnp3d_dbg, dict) and pnp3d_dbg.get("reason") == "scene_required":
                scene_result = {
                    "ok": False,
                    "reason": "scene_required",
                    "scenes": pnp3d_dbg.get("scenes") or [],
                }

            if obj_corners_3d is None:
                pnp_result = {"error": "3d_pnp_corners_missing", "dbg": pnp3d_dbg}
            else:
                # 2) JSON에서 windows 전체를 가져와서 "best window"를 고르기 위해
                #    load_windows...는 1개만 주니까, 여기서 json을 직접 다시 읽는다.
                #    (pnp3d_dbg["json_path"]는 확정)
                json_path = pnp3d_dbg.get("json_path")
                if not json_path or not Path(json_path).exists():
                    pnp_result = {"error": "json_path_missing_or_not_found", "dbg": pnp3d_dbg}
                else:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    windows = None
                    if isinstance(data, dict) and isinstance(data.get("windows"), list):
                        windows = data["windows"]
                    elif isinstance(data, list):
                        windows = data
                    else:
                        windows = []

                    # 3) 후보 만들기: pnp_corners_4 있는 window만
                    cand_windows = []
                    for w in windows:
                        c4 = w.get("pnp_corners_4")
                        if isinstance(c4, list) and len(c4) == 4:
                            cand_windows.append(w)

                    if not cand_windows:
                        pnp_result = {"error": "no_valid_pnp_corners_4_in_json", "dbg": pnp3d_dbg}
                    else:
                        dist = np.zeros((4, 1), dtype=np.float32)

                        # 4) (window 후보) x (fov 후보) 중 reproj err 최소를 고른다
                        fov_candidates = [35, 40, 45, 50, 55, 60, 65, 70, 75, 85]
                        best = None
                        # best = (err, fov, K, rvec, tvec, R, picked_window_dict, obj3d_used)

                        for w in cand_windows:
                            c4_3d = w.get("pnp_corners_4")
                            if not (isinstance(c4_3d, list) and len(c4_3d) == 4):
                                continue

                            obj3d = order_3d_tl_tr_br_bl(c4_3d)  # TL,TR,BR,BL 정렬

                            for fov in fov_candidates:
                                Kt = make_K_from_fov(Wimg, H, fov_deg=float(fov))
                                rvec, tvec, R = solve_pnp_from_4pts(
                                    obj3d.tolist(),
                                    img_corners_2d.tolist(),
                                    Kt.tolist(),
                                    dist=dist
                                )

                                # 카메라 앞쪽
                                if float(tvec.reshape(-1)[2]) <= 0:
                                    continue

                                e = reproj_error(obj3d, img_corners_2d, rvec, tvec, Kt, dist=dist)

                                if best is None or e < best[0]:
                                    picked_window = {
                                        "id": w.get("id"),
                                        "asset_id": w.get("asset_id"),
                                        "size": w.get("size"),
                                    }
                                    best = (float(e), float(fov), Kt, rvec, tvec, R, picked_window, obj3d)

                        if best is None:
                            pnp_result = {"error": "pnp_failed_all_candidates", "dbg": pnp3d_dbg}
                        else:
                            best_err, best_fov, K_best, rvec_best, tvec_best, R_best, picked_window, obj3d_best = best

                            print("[PNP] picked_window =", picked_window, "best_fov =", best_fov, "best_err =",
                                  best_err)

                            # 5) reprojection debug viz (초록=실제2D, 빨강=재투영)
                            try:
                                H_img, W_img = img.shape[:2]
                                ts_ms = int(time.time() * 1000)

                                def _pt_clamp(x, y, W, H, pad=2):
                                    xi = int(round(float(x)))
                                    yi = int(round(float(y)))
                                    xi = max(pad, min(W - 1 - pad, xi))
                                    yi = max(pad, min(H - 1 - pad, yi))
                                    return xi, yi

                                def _text_pos(x, y, W, H, dx=6, dy=6, pad=2):
                                    return _pt_clamp(float(x) + dx, float(y) + dy, W, H, pad=pad)

                                # --- (A) 입력 2D만 찍은 디버그 (PnP에 들어간 점이 "창 코너"인지 확인) ---
                                try:
                                    dbg_in = img.copy()
                                    c2 = img_corners_2d.reshape(-1, 2)
                                    for i in range(4):
                                        x2, y2 = _pt_clamp(c2[i, 0], c2[i, 1], W_img, H_img)
                                        tx2, ty2 = _text_pos(c2[i, 0], c2[i, 1], W_img, H_img)
                                        cv2.circle(dbg_in, (x2, y2), 10, (0, 255, 0), -1)
                                        cv2.putText(dbg_in, f"IN-{i}", (tx2, ty2),
                                                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

                                    in_path = os.path.join(RESULT_DIR, f"pnp_2d_input_debug_{ts_ms}.png")
                                    ok_in = cv2.imwrite(in_path, dbg_in)
                                    print("[PNP] 2d input debug saved ->", in_path, "ok=", ok_in)
                                except Exception as e:
                                    print("[PNP][WARN] 2d input debug save failed:", e)

                                # --- (B) window_info corners를 그대로 찍는 디버그 (window_info 자체가 이상한지 확인) ---
                                try:
                                    dbg_win = img.copy()
                                    w2 = np.array(window_info["corners_4"], dtype=np.float32).reshape(-1, 2)
                                    for i in range(4):
                                        xw, yw = _pt_clamp(w2[i, 0], w2[i, 1], W_img, H_img)
                                        txw, tyw = _text_pos(w2[i, 0], w2[i, 1], W_img, H_img)
                                        cv2.circle(dbg_win, (xw, yw), 10, (255, 0, 255), -1)
                                        cv2.putText(dbg_win, f"WIN-{i}", (txw, tyw),
                                                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 255), 2)

                                    win_path = os.path.join(RESULT_DIR, f"pnp_windowinfo_corners_debug_{ts_ms}.png")
                                    ok_win = cv2.imwrite(win_path, dbg_win)
                                    print("[PNP] window corners debug saved ->", win_path, "ok=", ok_win)
                                except Exception as e:
                                    print("[PNP][WARN] window corners debug save failed:", e)

                                # --- (C) reprojection 디버그 (초록=입력2D, 빨강=재투영) ---
                                proj, _ = cv2.projectPoints(
                                    obj3d_best.astype(np.float32), rvec_best, tvec_best, K_best, dist
                                )
                                proj = proj.reshape(-1, 2)

                                # =========================
                                # PNP RAW PROJECTION CHECK (OOB 확인)
                                # =========================
                                print("\n[PNP][PROJ_RAW]", proj.tolist())
                                print("[PNP][2D_RAW]", img_corners_2d.tolist())

                                for i in range(4):
                                    x = float(proj[i, 0])
                                    y = float(proj[i, 1])
                                    oob = (x < 0 or x >= W_img or y < 0 or y >= H_img)
                                    print(f"[PNP][PROJ_OOB] i={i} x={x:.2f} y={y:.2f} oob={oob}")
                                print()

                                dbg_img = img.copy()
                                c2 = img_corners_2d.reshape(-1, 2)

                                for i in range(4):
                                    x2, y2 = _pt_clamp(c2[i, 0], c2[i, 1], W_img, H_img)
                                    xr, yr = _pt_clamp(proj[i, 0], proj[i, 1], W_img, H_img)

                                    cv2.circle(dbg_img, (x2, y2), 8, (0, 255, 0), -1)  # 2D green
                                    cv2.circle(dbg_img, (xr, yr), 8, (0, 0, 255), -1)  # reproj red
                                    # 2D-3D 오차를 선으로 표시 (cyan)
                                    cv2.line(dbg_img, (x2, y2), (xr, yr), (255, 255, 0), 2)

                                    tx2, ty2 = _text_pos(c2[i, 0], c2[i, 1], W_img, H_img)
                                    txr, tyr = _text_pos(proj[i, 0], proj[i, 1], W_img, H_img)

                                    cv2.putText(dbg_img, f"2D-{i}", (tx2, ty2),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                                    cv2.putText(dbg_img, f"3D-{i}", (txr, tyr),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                                dbg_path = os.path.join(RESULT_DIR, f"pnp_reproj_debug_{ts_ms}.png")
                                ok = cv2.imwrite(dbg_path, dbg_img)
                                print("[PNP] reproj debug saved ->", dbg_path, "ok=", ok)

                            except Exception as e:
                                print("[PNP][WARN] reproj debug save failed:", e)

                            # 6) 품질 컷 (권장)
                            tz = float(tvec_best.reshape(-1)[2])
                            if tz <= 0:
                                pnp_result = {"error": "tvec_z<=0", "tvec_z": tz, "dbg_3d": pnp3d_dbg}
                            elif best_err > 15.0:
                                pnp_result = {
                                    "error": "reproj_err_too_large",
                                    "reproj_err_px": float(best_err),
                                    "used_fov": float(best_fov),
                                    "picked_window": picked_window,
                                    "dbg_3d": pnp3d_dbg,
                                    "note": "PnP rejected by reprojection error cutoff",
                                }
                            else:
                                pnp_result = _pack_pnp_success(
                                    K_use=K_best,
                                    rvec_use=rvec_best,
                                    tvec_use=tvec_best,
                                    R_use=R_best,
                                    reproj_err_px=best_err,
                                    picked_window=picked_window,
                                    pnp3d_dbg=pnp3d_dbg,
                                    used_fov=best_fov
                                )

    except Exception as e:
        pnp_result = {"error": str(e), "note": "PnP failed (exception)"}

    # =========================
    # OUT (딱 1번만 생성)
    # =========================
    out = {
        "ts": float(time.time()),
        "image": image_path,
        "occ_mode": OCC_MODE,
        "depth_ok": bool(depth_ok),
        "max_n": int(use_max),
        "window_bbox": (list(win) if win is not None else None),
        "light_origin": [float(origin[0]), float(origin[1])],
        "best_spot": packed[0],
        "spots": packed,
        "window": window_info,
        "pnp": pnp_result,
        "scene": scene_result,
    }

    # =========================
    # WINDOW VIZ
    # =========================
    try:
        viz2 = img.copy()
        if win is not None:
            x, y, ww, hh = win
            cv2.rectangle(viz2, (x, y), (x + ww, y + hh), (0, 255, 255), 4)

            if windows_for_viz:
                poly = np.array(windows_for_viz[0]["corners_4"], dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(viz2, [poly], True, (0, 255, 255), 3)

        # =========================
        # PNP OVERLAY (MAIN WINDOW VIZ)
        # =========================
        if isinstance(pnp_result, dict) and pnp_result.get("K") and pnp_result.get("rvec"):
            try:
                Kp = np.array(pnp_result["K"], dtype=np.float32)
                rvecp = np.array(pnp_result["rvec"], dtype=np.float32).reshape(3, 1)
                tvecp = np.array(pnp_result["tvec"], dtype=np.float32).reshape(3, 1)

                # PnP에서 사용한 3D / 2D
                obj3d = obj3d_best.astype(np.float32)
                img2d = img_corners_2d.astype(np.float32)

                proj, _ = cv2.projectPoints(obj3d, rvecp, tvecp, Kp, None)
                proj = proj.reshape(-1, 2)

                for i in range(4):
                    x2, y2 = int(img2d[i, 0]), int(img2d[i, 1])
                    xr, yr = int(proj[i, 0]), int(proj[i, 1])

                    # input 2D (green)
                    cv2.circle(viz2, (x2, y2), 7, (0, 255, 0), -1)
                    # reprojection (red)
                    cv2.circle(viz2, (xr, yr), 7, (0, 0, 255), -1)
                    # error line (cyan)
                    cv2.line(viz2, (x2, y2), (xr, yr), (255, 255, 0), 2)

                    cv2.putText(viz2, f"2D-{i}", (x2 + 5, y2 + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    cv2.putText(viz2, f"3D-{i}", (xr + 5, yr + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

            except Exception as e:
                print("[VIZ][PNP_OVERLAY][WARN]", e)

        viz_ts = int(time.time() * 1000)
        viz_path2 = os.path.join(RESULT_DIR, f"result_latest_viz_window_{viz_ts}.png")
        ok = cv2.imwrite(viz_path2, viz2)
        print("[VIZ_WINDOW] saved ->", viz_path2, "ok=", ok)

        # ✅ fixed 파일을 항상 갱신
        if ok:
            fixed_viz_path = os.path.join(RESULT_DIR, "result_latest_viz.png")
            try:
                shutil.copyfile(viz_path2, fixed_viz_path)
                print("[VIZ] copied ->", fixed_viz_path, "ok=True")
            except Exception as e:
                print("[VIZ] copy failed ->", fixed_viz_path, "err=", e)


    except Exception as e:
        print("[WARN] VIZ_WINDOW save failed:", e)

    # =========================
    # spot_types summary
    # =========================
    type_summary = {"bright": 0, "medium": 0, "dim": 0}
    bias_summary = {"morning": 0, "noon": 0, "evening": 0, "unknown": 0}

    for s in packed:
        lp = s.get("light_profile", {})
        lvl = lp.get("level", "medium")
        bs = lp.get("bias", "unknown")
        type_summary[lvl] = int(type_summary.get(lvl, 0)) + 1
        bias_summary[bs] = int(bias_summary.get(bs, 0)) + 1

    out["spot_types"] = {"level_counts": type_summary, "bias_counts": bias_summary}

    # =========================
    # SAVE JSON
    # =========================
    if save_outputs:
        try:
            with open(RESULT_JSON_LATEST, "w", encoding="utf-8") as f:
                json.dump(to_jsonable(out), f, ensure_ascii=False, indent=2)
            print("[JSON] saved ->", RESULT_JSON_LATEST)
        except Exception as e:
            print("[WARN] json dump failed:", e)

    # =========================
    # DEBUG VIZ
    # =========================
    if debug_viz:
        try:
            best_xy = tuple((out.get("best_spot") or {}).get("pt") or (0, 0))
            print("[VIZ_MAIN] window_info corners_4 =", None if not window_info else window_info.get("corners_4"))
            print("[VIZ_MAIN] win bbox =", win)
            print("[VIZ_MAIN] best_xy =", best_xy)

            viz_main_path = os.path.join(RESULT_DIR, f"result_latest_viz_{int(time.time())}.png")

            draw_debug(
                image=img,
                floor_mask=(core > 0),
                windows=windows_for_viz,
                light_map=None,
                best_point=best_xy,
                save_path=viz_main_path
            )

            # print("[VIZ] saved ->", os.path.join(RESULT_DIR, "result_latest_viz.png"))
            print("[VIZ_MAIN] saved ->", viz_main_path)

        except Exception as e:
            print("[WARN] draw_debug failed:", e)

    return out