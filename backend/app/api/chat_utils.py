import os
import json
import time
import glob
import app.cv.pipeline as p

from datetime import datetime
from typing import Any, Dict, Optional, Tuple,  List

from pathlib import Path

from app.cv.pipeline import list_71765_scenes
from app.config import RESULT_DIR

from fastapi import Request

# =========================
# URL / PATH
# =========================
def abs_url(request: Request, path: str) -> str:
    base = str(request.base_url).rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def to_results_url(path_or_name: str) -> str:
    return f"/results/{os.path.basename(path_or_name)}"


def cache_bust_url(request: Request, path: str, ts_ms: Optional[int] = None) -> str:
    base = abs_url(request, path)
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    joiner = "&" if "?" in base else "?"
    return f"{base}{joiner}t={ts_ms}"


# =========================
# CLIENT / TIME
# =========================
def client_key_from_request(request: Request) -> str:
    """
    ⚠️ 단독 host 기반은 위험(NAT/공유IP로 세션 섞임).
    가능하면 sid/cid를 우선 사용.
    - sid: chat_session에서 발급한 세션 id (cookie)
    - cid: stream에서 내려준 client id (cookie)
    """
    # 1) sid cookie
    sid = request.cookies.get("sid")
    if sid:
        return str(sid)

    # 2) cid cookie
    cid = request.cookies.get("cid")
    if cid:
        return str(cid)

    # 3) fallback: host
    host = getattr(getattr(request, "client", None), "host", None) or "unknown"
    return str(host)


def now_kst_yyyymmdd_hhmm() -> Tuple[str, str]:
    now = datetime.now()
    return now.strftime("%Y%m%d"), now.strftime("%H%M")


# =========================
# RESULT FILES
# =========================
def load_latest_result() -> Dict[str, Any]:
    latest_json = os.path.join(RESULT_DIR, "result_latest.json")
    if not os.path.exists(latest_json):
        return {}
    try:
        with open(latest_json, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def pick_latest_result_file(prefix: str) -> Optional[str]:
    pattern = os.path.join(RESULT_DIR, f"{prefix}*.png")
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]


# =========================
# SCENE
# =========================

# 1) 수동 매핑(있으면 최우선)
SCENE_LABEL_MAP = {
    # TODO: 니 프로젝트에서 실제 scene id들 채워넣으면 100% 한글로 뜸
    # "etc_education_l_002": "교육 공간",
    # "living_room_xxx": "거실",
    # "bathroom_xxx": "욕실",
    # ...
}

def _guess_scene_label_from_id(scene_id: str) -> str:
    s = (scene_id or "").lower()

    # 2) 휴리스틱(매핑 없을 때라도 그럴듯하게)
    if "bath" in s or "toilet" in s or "restroom" in s:
        return "욕실"
    if "living" in s or "lounge" in s:
        return "거실"
    if "bed" in s or "bedroom" in s:
        return "침실"
    if "kitchen" in s:
        return "주방"
    if "office" in s or "work" in s:
        return "사무/작업 공간"
    if "education" in s or "study" in s:
        return "교육/학습 공간"

    # fallback: 보기 좋게만
    return scene_id

# =========================
# Scene id -> label mapping
# =========================
_SCENE_LABEL_MAP: Optional[Dict[str, str]] = None
_SCENE_META_CACHE: Dict[str, Dict[str, Any]] = {}

def _candidate_scene_roots() -> List[str]:
    """
    scene 메타(.json)들이 있을 법한 루트 후보들.
    - 환경변수 우선
    - 프로젝트 내부/상위 폴더
    - 사용자 Desktop/71765_json (네 로그에 실제로 등장)
    """
    roots: List[str] = []

    # 1) env 우선
    for k in ("SCENE_DATA_DIR", "SCENE_META_DIR", "DATA_71765_DIR", "DIR_71765_JSON", "AIGHUB_71765_DIR"):
        v = os.getenv(k)
        if v and os.path.isdir(v):
            roots.append(v)

    # 2) 프로젝트 상대경로 후보
    try:
        from app.config import BASE_DIR
        base = str(BASE_DIR)
        for rel in ("71765_json", "data/71765_json", "../71765_json", "../data/71765_json"):
            p = os.path.abspath(os.path.join(base, rel))
            if os.path.isdir(p):
                roots.append(p)
    except Exception:
        pass

    # 3) 사용자 Desktop 후보 (네 로그: C:\\Users\\...\\Desktop\\71765_json\\...)
    try:
        desktop = str(Path.home() / "Desktop" / "71765_json")
        if os.path.isdir(desktop):
            roots.append(desktop)
    except Exception:
        pass

    # 중복 제거(순서 유지)
    seen = set()
    out: List[str] = []
    for r in roots:
        rr = os.path.abspath(r)
        if rr not in seen:
            seen.add(rr)
            out.append(rr)
    return out


def _find_scene_meta_json(scene_id: str) -> Optional[str]:
    """
    scene_id.json 파일 경로를 찾는다.
    후보 루트들에서만 recursive glob로 탐색한다.
    """
    sid = (scene_id or "").strip()
    if not sid:
        return None

    cached_path = _SCENE_META_CACHE.get(f"__path__:{sid}")
    if isinstance(cached_path, dict) and cached_path.get("path"):
        p = str(cached_path["path"])
        if os.path.exists(p):
            return p

    roots = _candidate_scene_roots()
    if not roots:
        return None

    patterns = [
        os.path.join("**", sid, f"{sid}.json"),
        os.path.join("**", f"{sid}.json"),
    ]

    for root in roots:
        for pat in patterns:
            hits = glob.glob(os.path.join(root, pat), recursive=True)
            if hits:
                path = hits[0]
                _SCENE_META_CACHE[f"__path__:{sid}"] = {"path": path}
                return path

    return None


def _read_scene_meta(scene_id: str) -> Optional[Dict[str, Any]]:
    """
    scene_id.json을 읽어서 dict 반환
    """
    sid = (scene_id or "").strip()
    if not sid:
        return None

    if sid in _SCENE_META_CACHE:
        v = _SCENE_META_CACHE.get(sid)
        if isinstance(v, dict):
            return v

    path = _find_scene_meta_json(sid)
    if not path:
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            _SCENE_META_CACHE[sid] = obj
            return obj
    except Exception:
        return None

    return None


def _label_from_scene_meta(scene_id: str) -> Optional[str]:
    """
    metadata에서 사람이 읽을 label 생성:
    예) "주거시설 / 원룸 / 소형(~60m²)"
    """
    obj = _read_scene_meta(scene_id)
    if not isinstance(obj, dict):
        return None

    meta = obj.get("metadata")
    if not isinstance(meta, dict):
        return None

    space_class = meta.get("space_class")
    space_subclass = meta.get("space_subclass")
    space_detail = meta.get("space_detail")

    parts: List[str] = []
    if isinstance(space_class, str) and space_class.strip():
        parts.append(space_class.strip())
    if isinstance(space_subclass, str) and space_subclass.strip():
        parts.append(space_subclass.strip())
    if isinstance(space_detail, str) and space_detail.strip():
        parts.append(space_detail.strip())

    if parts:
        return " / ".join(parts)

    fn = meta.get("file_name")
    if isinstance(fn, str) and fn.strip():
        return fn.strip()

    return None


def _load_scene_label_map() -> Dict[str, str]:
    """
    1) pipeline에 매핑 dict가 있으면 사용
    2) list_71765_scenes()에서 id들을 받아서 metadata 기반 label 생성
    3) 실패하면 빈 dict
    """
    # 1) pipeline 내부에 매핑 dict가 정의돼 있는지 확인
    try:
        for attr in (
            "SCENE_ID_TO_LABEL",
            "SCENE_ID_TO_NAME",
            "SCENE_LABELS",
            "SCENE_MAP",
            "SCENE_ID_TO_KO",
            "SCENE_ID_TO_NAME_KO",
        ):
            m = getattr(p, attr, None)
            if isinstance(m, dict) and m:
                return {
                    str(k): str(v)
                    for k, v in m.items()
                    if str(k).strip() and isinstance(v, str) and str(v).strip()
                }
    except Exception:
        pass

    # 2) list_71765_scenes()에서 scene id들을 얻어 label 생성
    m2: Dict[str, str] = {}
    try:
        raw = list_71765_scenes()

        if isinstance(raw, list):
            for x in raw:
                sid = None
                if isinstance(x, str):
                    sid = x
                elif isinstance(x, dict):
                    sid = x.get("id") or x.get("scene_id") or x.get("sceneId") or x.get("value")

                if not isinstance(sid, str) or not sid.strip():
                    continue
                sid = sid.strip()

                lbl = _label_from_scene_meta(sid) or sid
                m2[sid] = lbl

        elif isinstance(raw, dict):
            for k in raw.keys():
                sid = str(k).strip()
                if not sid:
                    continue
                lbl = _label_from_scene_meta(sid) or sid
                m2[sid] = lbl

    except Exception:
        pass

    return m2

# =========================
# Scene meta/assets reader + room label inference
# =========================

from typing import Tuple

def read_scene_json(scene_id: str) -> Optional[Dict[str, Any]]:
    """
    ✅ scene_id.json 전체 내용을 읽어 반환한다.
    - 내부적으로 _read_scene_meta()를 그대로 사용 (우리가 이미 경로 찾기+캐시 구현함)
    - 반환값은 json dict (metadata, assets 포함)
    """
    sid = (scene_id or "").strip()
    if not sid:
        return None
    return _read_scene_meta(sid)


def _asset_tokens(scene_obj: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    scene json에서 assets를 읽어:
    - subclasses: ['bed', 'toilet', 'bathtap', ...]
    - classes: ['bathroom_furniture', 'opening', ...]
    """
    subclasses: List[str] = []
    classes: List[str] = []

    assets = scene_obj.get("assets")
    if not isinstance(assets, list):
        return subclasses, classes

    for a in assets:
        if not isinstance(a, dict):
            continue
        sc = a.get("subclass")
        cl = a.get("class")

        if isinstance(sc, str) and sc.strip():
            subclasses.append(sc.strip().lower())
        if isinstance(cl, str) and cl.strip():
            classes.append(cl.strip().lower())

    return subclasses, classes


def infer_room_label_from_assets(scene_id: str) -> Optional[str]:
    """
    assets[] 기반으로 욕실/침실/주방/거실을 추론한다.

    ✅ 개선 목표:
    - '욕실' 과대판정 방지 (toilet 하나 있다고 욕실 확정 금지)
    - 침실/주방은 명확 신호가 있으면 우선 확정
    - 욕실은 강한 조합(toilet + washstand/샤워/욕조) 또는 bathroom_furniture 다수일 때만 확정
    """

    obj = read_scene_json(scene_id)
    if not isinstance(obj, dict):
        return None

    subclasses, classes = _asset_tokens(obj)
    sub = set(subclasses)

    # -------------------------
    # 1) 강한 확정 규칙(우선)
    # -------------------------

    # ✅ 주방 확정 조건 강화: cooktop 단독이면 확정하지 않음
    # cooktop + (refrigerator/microwave/oven/diningtable) 중 1개 이상일 때만 확정
    if "cooktop" in sub:
        if ("refrigerator" in sub) or ("microwave" in sub) or ("oven" in sub) or ("diningtable" in sub):
            return "주방"

    # 욕실 강신호 카운트
    # - toilet이 있어야 욕실 가능성이 커짐
    # - toilet + (washstand/bathtap/showerhead) 중 하나 이상이면 확정
    bathroom_strong = 0
    has_toilet = ("toilet" in sub)

    if has_toilet:
        bathroom_strong += 1
        if "washstand" in sub:
            bathroom_strong += 1
        if "bathtap" in sub or "bathtub" in sub:
            bathroom_strong += 1
        if "showerhead" in sub:
            bathroom_strong += 1

    bathroom_class_cnt = classes.count("bathroom_furniture")

    # ✅ 욕실 확정 조건을 "빡세게"
    # - toilet + 다른 욕실 설비 1개 이상
    # - 또는 bathroom_furniture가 매우 많을 때
    if (has_toilet and bathroom_strong >= 2) or (bathroom_class_cnt >= 4 and (has_toilet or "washstand" in sub)):
        return "욕실"

    # -------------------------
    # 2) 애매한 경우: 점수 기반
    # -------------------------
    living = 0
    kitchen = 0
    bathroom = 0
    bedroom = 0

    # ---- 욕실(약하게만) ----
    # toilet 단독은 과대판정 원인이라 점수 낮춤
    if "toilet" in sub:
        bathroom += 1
    if "washstand" in sub:
        bathroom += 1
    if "showerhead" in sub:
        bathroom += 1
    if "bathtap" in sub or "bathtub" in sub:
        bathroom += 1

    # bathroom_furniture가 조금 있다고 욕실로 확정되지 않도록 cap 적용
    if bathroom_class_cnt > 0:
        bathroom += 1 if bathroom_class_cnt >= 2 else 0

    # ---- 주방 ----
    # cooktop 없으면 애매하니 점수만
    if "refrigerator" in sub:
        kitchen += 2
    if "microwave" in sub or "oven" in sub:
        kitchen += 1
    if "diningtable" in sub:
        kitchen += 1

    # sink는 욕실/주방 공통이라 주방에만 약하게
    if "sink" in sub:
        kitchen += 1

    # ---- 거실 ----
    if "tv" in sub:
        living += 2
    if "sofa" in sub:
        living += 2
    if "chair" in sub:
        living += 1
    if "table" in sub:
        living += 1
    if "cabinet" in sub:
        living += 1

    # ---- 침실(약신호) ----
    if "wardrobe" in sub or "dresser" in sub:
        bedroom += 1

    scores = {
        "거실": living,
        "주방": kitchen,
        "욕실": bathroom,
        "침실": bedroom,
    }

    best_label, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score <= 0:
        return None

    return best_label

def scene_id_to_meta_label(scene_id: str) -> Optional[str]:
    obj = read_scene_json(scene_id)
    if not isinstance(obj, dict):
        return None

    md = obj.get("metadata")
    if not isinstance(md, dict):
        return None

    # 예: "주거시설 / 원룸 / 소형(~60m²)"
    cls = md.get("space_class")
    sub = md.get("space_subclass")
    detail = md.get("space_detail")

    parts = [p for p in [cls, sub, detail] if isinstance(p, str) and p.strip()]
    if not parts:
        return None
    return " / ".join(parts)


def scene_id_to_room_label(scene_id: str) -> str:
    """
    드롭다운은 '71765 3D scene 선택' 용도다.
    residence_house_*는 원룸/투룸(주거 타입) 모델이므로,
    assets로 '주방/침실' 같은 방 라벨을 억지로 뽑지 않는다.

    label 정책:
    - residence_house_1_*  -> "원룸"
    - residence_house_2_*  -> "투룸"
    - etc_*                -> metadata 기반 (기타시설/교육/...) or fallback
    """
    if not isinstance(scene_id, str) or not scene_id.strip():
        return "선택"

    sid = scene_id.strip()

    # ✅ 주거시설(원룸/투룸) 라벨은 id prefix로 결정
    if sid.startswith("residence_house_1_"):
        return "원룸"
    if sid.startswith("residence_house_2_"):
        return "투룸"

    # ✅ 기타 scene은 metadata 기반으로 사람이 읽게
    md_label = scene_id_to_meta_label(sid)  # 너가 이미 metadata 읽는 함수가 있다면 그걸 사용
    if isinstance(md_label, str) and md_label.strip():
        return md_label.strip()

    # fallback
    return sid



def scene_to_label(s: Any) -> str:
    """
    ✅ 핵심: scene_id -> 한글 라벨
    - id면: label map 조회 -> 없으면 metadata에서 생성 -> 없으면 id 그대로
    - dict면: id 뽑아서 동일 처리
    """
    global _SCENE_LABEL_MAP

    if _SCENE_LABEL_MAP is None:
        _SCENE_LABEL_MAP = _load_scene_label_map()

    # str 입력
    if isinstance(s, str):
        sid = s.strip()
        if not sid:
            return ""
        # 1) 미리 빌드된 맵
        lbl = (_SCENE_LABEL_MAP or {}).get(sid)
        if isinstance(lbl, str) and lbl.strip():
            return lbl
        # 2) 메타에서 즉시 생성
        lbl2 = _label_from_scene_meta(sid)
        if isinstance(lbl2, str) and lbl2.strip():
            # 캐시 추가
            if _SCENE_LABEL_MAP is not None:
                _SCENE_LABEL_MAP[sid] = lbl2
            return lbl2
        return sid

    # dict 입력
    if isinstance(s, dict):
        sid = s.get("id") or s.get("scene_id") or s.get("sceneId") or s.get("value")
        if isinstance(sid, str) and sid.strip():
            return scene_to_label(sid.strip())
        # dict에 label/name이 직접 있으면 fallback
        lab = s.get("label") or s.get("name")
        if isinstance(lab, str) and lab.strip():
            return lab.strip()

    # 기타 타입
    try:
        return str(s)
    except Exception:
        return ""


# =========================
# SAFE PARSE
# =========================
def safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def parse_hh_from_any(v) -> Optional[int]:
    """
    "HHMM" / "HH:MM" / "HH" / int / float 대응
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        hh = int(v)
        return hh if 0 <= hh <= 23 else None

    s = str(v).strip()
    if not s:
        return None

    if ":" in s:
        try:
            hh = int(s.split(":")[0])
            return hh if 0 <= hh <= 23 else None
        except Exception:
            return None

    if len(s) >= 2 and s[:2].isdigit():
        try:
            hh = int(s[:2])
            return hh if 0 <= hh <= 23 else None
        except Exception:
            return None

    return None


# =========================
# BEST POINT
# =========================
def extract_best_point(data: Dict[str, Any]) -> Optional[Any]:
    if not isinstance(data, dict):
        return None

    best_spot = data.get("best_spot")
    if isinstance(best_spot, dict):
        pt = best_spot.get("pt")
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            return pt

    spots = data.get("spots")
    if isinstance(spots, list) and spots:
        s0 = spots[0]
        if isinstance(s0, dict):
            pt = s0.get("pt")
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                return pt

    bp = data.get("best_point")
    if isinstance(bp, (list, tuple)) and len(bp) >= 2:
        return bp
    if isinstance(bp, dict) and ("x" in bp and "y" in bp):
        return bp

    return None


# =========================
# META → LAT/LON
# =========================
def get_lat_lot_from_meta(meta):
    import json

    if meta is None:
        return None

    # str -> dict
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            return None

    if not isinstance(meta, dict):
        return None

    # ✅ 후보 dict들을 순서대로 훑기 (중첩 구조 대비)
    candidates = [meta]
    for k in ("location", "coords", "gps", "geo"):
        v = meta.get(k)
        if isinstance(v, dict):
            candidates.append(v)

    def pick(d: dict):
        lat = d.get("lat", d.get("latitude"))
        lot = d.get("lot")
        if lot is None: lot = d.get("lon")
        if lot is None: lot = d.get("lng")
        if lot is None: lot = d.get("longitude")
        if lat is None or lot is None:
            return None
        try:
            return {"lat": float(lat), "lot": float(lot)}
        except Exception:
            return None

    for d in candidates:
        out = pick(d)
        if out:
            return out

    return None


# =========================
# JSON SAFE (추가)
# =========================
def to_jsonable(x: Any) -> Any:
    """
    json.dump 실패 방지용.
    - numpy/torch 등 객체가 섞일 때 대비
    """
    try:
        json.dumps(x, ensure_ascii=False)
        return x
    except Exception:
        return str(x)


def read_json_safely(path: str) -> Dict[str, Any]:
    """
    결과 json 읽기 공통화 (load_latest_result랑 역할 분리 가능)
    """
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}