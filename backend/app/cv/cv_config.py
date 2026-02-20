"""
CV 파이프라인/유틸 공통 설정값(상수) 모음.
pipeline.py, utils.py 등에서 공유해서 ImportError/NameError 방지.
"""

# 후보/클러스터
CAND_STEP = 18
MAX_N = 6
CLUSTER_DIST = 55

# surface penalty
SURFACE_PENALTY = 25.0
SURFACE_PENALTY_ONLY_IF_HAS_FLOOR = True

# ray/light sampling
WINDOW_SAMPLES = 9
RAY_SAMPLES = 22

# depth occlusion
DEPTH_OCC_THRESHOLD = 0.06
OCC_MODE = "v8"
OCCLUSION_WEIGHT_V8 = 0.55
OCCLUSION_STRENGTH_V7 = 0.65

# score weights
W = {
    "LIGHT": 0.68,
    "WALL":  0.16,
    "PATH":  0.55,   # (현재 score에 미사용)
    "STAB":  0.25,
}

# thresholds
MIN_WALL = 0.15
MIN_STAB = 0.05

# plant penalty (현재는 spot 점수에서 분리했다고 했지만 혹시 남아있을 수 있음)
PLANT_PENALTY = 0.25

# 창/경계 과근접 후보 제거용
MIN_ORIGIN_DIST_PX = 140
MIN_WALL_FOR_BEST = 0.28
BEST_STAB_BONUS = 0.12
