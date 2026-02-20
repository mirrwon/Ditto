import axios from 'axios';
import { expireSession, isSessionExpired, touchActivity } from './session';

const AUTH_401_DETAILS = new Set([
  'Could not validate credentials',
  'Invalid token',
  'Not authenticated',
]);

const shouldExpireSessionFor401 = (error) => {
  if (error?.response?.status !== 401) return false;

  const wwwAuthenticate = String(
    error?.response?.headers?.['www-authenticate'] || ''
  ).toLowerCase();
  if (wwwAuthenticate.includes('bearer')) return true;

  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && AUTH_401_DETAILS.has(detail.trim())) {
    return true;
  }
  return false;
};

const api = axios.create({
  baseURL: 'http://localhost:8000',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  if (isSessionExpired()) {
    expireSession();
    return Promise.reject(new Error('Session expired'));
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    touchActivity();
    return response;
  },
  (error) => {
    if (shouldExpireSessionFor401(error)) {
      expireSession();
    }
    return Promise.reject(error);
  }
);

export default api; 
