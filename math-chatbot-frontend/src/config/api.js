const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const COGNITIVE_API_BASE_URL = import.meta.env.VITE_COGNITIVE_API_BASE_URL || 'http://127.0.0.1:8001';

export const API_BASE = API_BASE_URL.replace(/\/$/, '');
export const WS_BASE = API_BASE.replace(/^http/i, 'ws');
export const COGNITIVE_API_BASE = COGNITIVE_API_BASE_URL.replace(/\/$/, '');
export const COGNITIVE_WS_BASE = COGNITIVE_API_BASE.replace(/^http/i, 'ws');
