const STORAGE_KEY_USER = "user";
const STORAGE_KEY_LAST_ACTIVITY = "lastActivity";

export const IDLE_TIMEOUT_MS = 600 * 600 * 1000;
export const SESSION_EXPIRED_EVENT = "session-expired";

const readLastActivity = () => {
  const raw = localStorage.getItem(STORAGE_KEY_LAST_ACTIVITY);
  const ts = Number(raw);
  return Number.isFinite(ts) ? ts : null;
};

export const touchActivity = () => {
  localStorage.setItem(STORAGE_KEY_LAST_ACTIVITY, String(Date.now()));
};

export const isSessionExpired = (now = Date.now()) => {
  const last = readLastActivity();
  if (!last) return false;
  return now - last > IDLE_TIMEOUT_MS;
};

export const clearSession = () => {
  localStorage.removeItem(STORAGE_KEY_USER);
  localStorage.removeItem(STORAGE_KEY_LAST_ACTIVITY);
};

export const expireSession = () => {
  clearSession();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
};

export const storeUser = (user) => {
  if (!user || typeof user !== "object") return;
  const { accessToken, ...rest } = user;
  localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(rest));
  touchActivity();
};

export const readStoredUser = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_USER);
    if (!raw) return null;
    const user = JSON.parse(raw);
    if (!user) return null;

    if (user?.accessToken) {
      delete user.accessToken;
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
    }


    const last = readLastActivity();
    if (!last) {
      touchActivity();
      return user;
    }

    if (isSessionExpired()) {
      expireSession();
      return null;
    }

    return user;
  } catch (error) {
    return null;
  }
};

export const fetchWithSession = async (input, init = {}) => {
  if (isSessionExpired()) {
    expireSession();
    throw new Error("Session expired");
  }

  const headers = {
    ...(init.headers || {}),
  };

  const nextInit = {
    ...init,
    headers,
    credentials: "include",
  };

  const response = await fetch(input, nextInit);

  if (response.ok) {
    touchActivity();
  } else if (response.status === 401) {
    expireSession();
  }

  return response;
};
