/**
 * API Client - Axios configuration with interceptors
 *
 * Features:
 * - Automatic token injection from localStorage
 * - Global error handling with toast notifications
 * - 401 redirect to login
 * - Request/response logging in development
 *
 * Ref: skills/react-typescript/SKILL.md
 */

import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import toast from 'react-hot-toast';

const TOKEN_KEY = 'auth_token';

// Create axios instance
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Request interceptor - Add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Inject authentication token
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Log request in development
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.data);
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors
apiClient.interceptors.response.use(
  (response) => {
    // Log response in development
    if (import.meta.env.DEV) {
      console.log(`[API] Response ${response.status}`, response.data);
    }
    return response;
  },
  (error: AxiosError<{ message?: string; detail?: string }>) => {
    const status = error.response?.status;
    const message = error.response?.data?.message || error.response?.data?.detail;

    // Handle different error status codes
    switch (status) {
      case 401:
        // Unauthorized - Token expired or invalid
        toast.error('Sesión expirada. Por favor, inicia sesión nuevamente.');
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem('auth_user');
        // Redirect to login after a short delay
        setTimeout(() => {
          window.location.href = '/login';
        }, 1500);
        break;

      case 403:
        // Forbidden - No permission
        toast.error(message || 'No tienes permisos para realizar esta acción.');
        break;

      case 404:
        // Not found
        toast.error(message || 'Recurso no encontrado.');
        break;

      case 409:
        // Conflict - Duplicate or business logic error
        toast.error(message || 'El recurso ya existe o hay un conflicto.');
        break;

      case 422:
        // Validation error
        toast.error(message || 'Error de validación. Verifica los datos ingresados.');
        break;

      case 429:
        // Too many requests
        toast.error('Demasiadas solicitudes. Intenta nuevamente más tarde.');
        break;

      case 500:
      case 502:
      case 503:
        // Server errors
        toast.error(
          message || 'Error del servidor. Por favor, intenta nuevamente más tarde.'
        );
        break;

      default:
        // Network error or unknown error
        if (!error.response) {
          toast.error('Error de conexión. Verifica tu conexión a internet.');
        } else {
          toast.error(message || 'Ocurrió un error inesperado.');
        }
    }

    // Log error in development
    if (import.meta.env.DEV) {
      console.error('[API] Error:', {
        status,
        message,
        url: error.config?.url,
        method: error.config?.method,
      });
    }

    return Promise.reject(error);
  }
);

export default apiClient;
