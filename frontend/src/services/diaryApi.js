import api from "./api";

const API_BASE = "/api/diary";

export const diaryApi = {
  getList: () => api.get(API_BASE),

  create: (formData) =>
    api.post(API_BASE, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  update: (id, formData) =>
    api.put(`${API_BASE}/${id}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
};