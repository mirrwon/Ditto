//페이지 이동 사이에서 사진 잃어버리지 않게 임시 보관하는 장치

const KEY = "pendingDiaryPhoto";

export function readPendingDiaryPhoto() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearPendingDiaryPhoto() {
  try {
    localStorage.removeItem(KEY);
  } catch {}
}
