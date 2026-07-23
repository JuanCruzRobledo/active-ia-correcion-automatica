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
import { isAuthEndpoint } from './auth-endpoints';
import { extractDetailMessage, type ApiErrorDetailShape } from '../utils/apiError';

const TOKEN_KEY = 'auth_token';

// Create axios instance
// Ensure baseURL always includes /api/v1
const getBaseURL = () => {
  const envURL = import.meta.env.VITE_API_URL;

  // If no env URL, use default
  if (!envURL) {
    return '/api/v1';
  }

  // If env URL already includes /api/v1, use as is
  if (envURL.includes('/api/v1')) {
    return envURL;
  }

  // Otherwise, append /api/v1
  return `${envURL}/api/v1`;
};

export const apiClient = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 120 seconds (2 minutes) - increased for PDF/AI processing
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

/**
 * Global response-error handler for the axios interceptor.
 *
 * Exported so it can be unit-tested directly (feeding it a crafted AxiosError)
 * without reaching into axios internals. The interceptor below is registered
 * with this exact function.
 */
export function handleResponseError(
  error: AxiosError<{ message?: string; detail?: ApiErrorDetailShape }>
): Promise<never> {
  const status = error.response?.status;

  // For blob responses (file downloads), the error body arrives as a Blob and
  // can't be parsed as JSON. Skip global toasts — the calling function handles errors.
  if (error.response?.data instanceof Blob) {
    return Promise.reject(error);
  }

  // ERR-005: el `detail` puede ser string, array de validación (Pydantic) u
  // objeto { error_code, message } (errores de IA). Un único extractor los cubre.
  const message =
    error.response?.data?.message ||
    extractDetailMessage(error.response?.data?.detail);

  // Handle different error status codes
  switch (status) {
    case 401:
      // ERR-004: un 401 en un endpoint de auth (login / cambio de contraseña) NO
      // es sesión expirada, es credenciales inválidas. Preservamos el error (y su
      // mensaje real del backend) para que el caller lo muestre, SIN limpiar la
      // sesión ni redirigir. El resto de los 401 (token expirado en un endpoint
      // autenticado) mantienen el comportamiento de expiración.
      if (isAuthEndpoint(error.config?.url)) {
        return Promise.reject(error);
      }
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

    case 409: {
      // Fase 5 multi-tenant: `get_universidad_activa` responde 409 cuando la
      // sesión no tiene universidad activa resoluble (token viejo ambiguo:
      // 0 o 2+ membresías). El backend no manda un error_code para este caso
      // (sólo el string de detail), así que se distingue por contenido —
      // NO es el 409 genérico de "recurso duplicado".
      const sinUniversidadActiva = /eleg[ií].*universidad/i.test(message ?? '');
      toast.error(
        sinUniversidadActiva
          ? 'Elegí una universidad activa para continuar.'
          : message || 'El recurso ya existe o hay un conflicto.'
      );
      break;
    }

    case 424:
      // Sin credenciales/campus de Moodle configurados para la universidad
      // activa (moodle_credentials_resolver.py). El backend ya manda un
      // mensaje accionable; el fallback también remite al perfil.
      toast.error(
        message ||
          'Faltan las credenciales de Moodle de la universidad activa. Configurala en tu perfil.'
      );
      break;

    case 422:
      // Validation error
      toast.error(message || 'Error de validación. Verifica los datos ingresados.');
      break;

    case 402:
      // Payment required (Gemini API key invalid) — handled by specific hooks
      break;

    case 429:
      // Too many requests (Gemini rate limit) — handled by specific hooks
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

// Response interceptor - Handle errors
apiClient.interceptors.response.use(
  (response) => {
    // Log response in development
    if (import.meta.env.DEV) {
      console.log(`[API] Response ${response.status}`, response.data);
    }
    return response;
  },
  handleResponseError
);

export default apiClient;
