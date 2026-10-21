import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://data-insight-api-uybc.onrender.com/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Forecast API
export const forecastAPI = {
  getCities: () => api.get('/forecast/cities'),
  getCityForecast: (city) => api.get(`/forecast/${city}`),
  getAllForecasts: () => api.get('/forecast/all/latest'),
};

// Quality API
export const qualityAPI = {
  getFreshness: () => api.get('/quality/freshness'),
  getIssues: () => api.get('/quality/issues'),
  getStats: () => api.get('/quality/stats'),
};

// Agent API
export const agentAPI = {
  askQuestion: (question) => api.post('/agent/ask', { question }),
  getCorpusInfo: () => api.get('/agent/corpus-info'),
};

// Pipeline API
export const pipelineAPI = {
  triggerPipeline: () => api.post('/pipeline/trigger'),
  getPipelineStatus: () => api.get('/pipeline/status'),
  getLiveStats: () => api.get('/pipeline/stats/live'),
};

export default api;
