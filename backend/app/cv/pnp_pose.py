import numpy as np
import cv2

def solve_pnp_from_4pts(pnp_3d_4pts, img_2d_4pts, K, dist=None):
    """
    pnp_3d_4pts: (4,3) list/np array (TL,TR,BR,BL) 3D
    img_2d_4pts: (4,2) list/np array (TL,TR,BR,BL) pixel
    K: (3,3) camera matrix
    dist: distortion coeffs or None
    return: rvec, tvec, R (3x3)
    """
    objp = np.array(pnp_3d_4pts, dtype=np.float32).reshape(-1, 3)
    imgp = np.array(img_2d_4pts, dtype=np.float32).reshape(-1, 2)
    K = np.array(K, dtype=np.float32)

    if dist is None:
        dist = np.zeros((4, 1), dtype=np.float32)

    ok, rvec, tvec = cv2.solvePnP(
        objectPoints=objp,
        imagePoints=imgp,
        cameraMatrix=K,
        distCoeffs=dist,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not ok:
        raise RuntimeError("solvePnP failed")

    R, _ = cv2.Rodrigues(rvec)
    return rvec, tvec, R

def window_normal_world(R, face_axis="x"):
    """
    창문 면의 법선을 얻고 싶을 때.
    지금 우리는 'x가 두께'인 면을 선택했으니 법선은 로컬 x축 방향이라고 두고 시작.
    R은 world_from_object(=Rodrigues 결과) 가정.
    반환 normal (3,)
    """
    if face_axis == "x":
        n = R @ np.array([1.0, 0.0, 0.0], dtype=np.float32)
    elif face_axis == "z":
        n = R @ np.array([0.0, 0.0, 1.0], dtype=np.float32)
    else:
        n = R @ np.array([0.0, 1.0, 0.0], dtype=np.float32)

    n = n / (np.linalg.norm(n) + 1e-9)
    return n
