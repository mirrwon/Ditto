import api from "./api";

export const login = (data) => api.post("/api/auth/login", data);

export const register = (payload) => {
  const formData = new FormData();

  Object.entries(payload).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      formData.append(key, value);
    }
  });

  return api.post("/api/auth/register", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
};

export const updateProfile = (payload) => {
  const formData = new FormData();

  Object.entries(payload).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      formData.append(key, value);
    }
  });

  return api.put("/api/auth/profile", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
};
