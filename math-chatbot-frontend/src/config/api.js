const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const API_BASE = API_BASE_URL.replace(/\/$/, '');
export const WS_BASE = API_BASE.replace(/^http/i, 'ws');
