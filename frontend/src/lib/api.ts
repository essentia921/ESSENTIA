import axios from 'axios';

// Su Vercel imposta VITE_API_URL con l'URL del backend Railway (es. https://xxx.up.railway.app/api).
// In locale/stesso host resta "/api".
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      const isAuthEndpoint = url.includes('/auth/');
      
      if (isAuthEndpoint || url === '/auth/me') {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  register: (data: { email: string; password: string; full_name?: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  googleLogin: () => (window.location.href = `${API_BASE_URL}/auth/google`),
  me: () => api.get('/auth/me'),
};

export const subscriptionAPI = {
  createCheckout: (data: { success_url: string; cancel_url: string; affiliate_code?: string }) =>
    api.post('/subscriptions/create-checkout-session', data),
  getStatus: () => api.get('/subscriptions/status'),
  cancel: () => api.post('/subscriptions/cancel'),
};

export const accountsAPI = {
  getAll: () => api.get('/accounts/'),
  create: (name: string) => api.post('/accounts/', { name }),
  rename: (id: number, name: string) => api.put(`/accounts/${id}`, { name }),
  delete: (id: number) => api.delete(`/accounts/${id}`),
};

export const profilesAPI = {
  get: (accountId: number, forceRefresh = false) =>
    api.get(`/profiles/${accountId}?force_refresh=${forceRefresh}`),
};

export const campaignsAPI = {
  get: (accountId: number, profileId: string, stateFilter?: string) =>
    api.get('/campaigns', {
      params: { account_id: accountId, profile_id: profileId, state_filter: stateFilter },
    }),
};

export const keywordsAPI = {
  get: (accountId: number, profileId: string, campaignIds: string[]) =>
    api.get('/keywords', {
      params: {
        account_id: accountId,
        profile_id: profileId,
        campaign_ids: campaignIds.join(','),
      },
    }),
};

export const bidsAPI = {
  update: (data: {
    account_id: number;
    profile_id: string;
    updates: { target_id: string; new_bid: number }[];
  }) => api.post('/bids/update', data),
};

export const booksAPI = {
  getAll: (params?: { profile_id?: string; account_id?: string }) =>
    api.get('/books/', { params }),
  getCombined: () => api.get('/books/combined'),
  syncFromAmazon: () => api.post('/books/sync-from-amazon'),
};

export const autopilotAPI = {
  getRuns: (params?: { account_id?: number; profile_id?: string; limit?: number }) =>
    api.get('/autopilot/runs', { params }),
};

export default api;
