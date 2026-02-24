/**
 * Shared TypeScript types for Active-IA frontend.
 *
 * These types mirror the backend Pydantic schemas to ensure type safety
 * across the full stack.
 *
 * IMPORTANT: Field names use snake_case to match the backend API responses.
 * If needed, transform to camelCase in service layer, not in types.
 *
 * Ref: backend/app/schemas/usuario.py
 * Ref: backend/app/schemas/auth.py
 * Ref: backend/app/models/enums.py
 * Ref: docs/specs/06-MODELO-DATOS.md
 */

// ===== ENUMS (using union types for erasableSyntaxOnly compatibility) =====

/**
 * User roles in the system.
 * Mirrors: backend/app/models/enums.py::RolEnum
 */
export type Rol = 'ADMIN' | 'COORDINADOR' | 'TUTOR';

/**
 * Rol values object for runtime usage (e.g., in dropdowns, validation).
 */
export const ROL = {
  ADMIN: 'ADMIN' as const,
  COORDINADOR: 'COORDINADOR' as const,
  TUTOR: 'TUTOR' as const,
} as const;

/**
 * Rubric types.
 * Mirrors: backend/app/models/enums.py::TipoRubricaEnum
 */
export type TipoRubrica =
  | 'TP'
  | 'PARCIAL_1'
  | 'PARCIAL_2'
  | 'RECUPERATORIO_1'
  | 'RECUPERATORIO_2'
  | 'FINAL'
  | 'GLOBAL';

/**
 * TipoRubrica values object for runtime usage.
 */
export const TIPO_RUBRICA = {
  TP: 'TP' as const,
  PARCIAL_1: 'PARCIAL_1' as const,
  PARCIAL_2: 'PARCIAL_2' as const,
  RECUPERATORIO_1: 'RECUPERATORIO_1' as const,
  RECUPERATORIO_2: 'RECUPERATORIO_2' as const,
  FINAL: 'FINAL' as const,
  GLOBAL: 'GLOBAL' as const,
} as const;

/**
 * Entrega (submission) status.
 * Mirrors: backend/app/models/enums.py::EstadoEntregaEnum
 */
export type EstadoEntrega = 'SUBIDA' | 'PENDIENTE' | 'CORREGIDA' | 'ERROR';

/**
 * EstadoEntrega values object for runtime usage.
 */
export const ESTADO_ENTREGA = {
  SUBIDA: 'SUBIDA' as const, // Uploaded, not corrected
  PENDIENTE: 'PENDIENTE' as const, // Being corrected
  CORREGIDA: 'CORREGIDA' as const, // Correction completed
  ERROR: 'ERROR' as const, // Process failed
} as const;

/**
 * Criterion evaluation status.
 * Mirrors: backend/app/models/enums.py::EstadoCriterioEnum
 */
export type EstadoCriterio = 'OK' | 'WARNING' | 'ERROR';

/**
 * EstadoCriterio values object for runtime usage.
 */
export const ESTADO_CRITERIO = {
  OK: 'OK' as const, // Criterion met satisfactorily
  WARNING: 'WARNING' as const, // Criterion with minor issues
  ERROR: 'ERROR' as const, // Criterion with significant problems
} as const;

/**
 * Rubric source.
 * Mirrors: backend/app/models/enums.py::FuenteRubricaEnum
 */
export type FuenteRubrica = 'manual' | 'pdf';

/**
 * FuenteRubrica values object for runtime usage.
 */
export const FUENTE_RUBRICA = {
  MANUAL: 'manual' as const,
  PDF: 'pdf' as const,
} as const;

// ===== USER TYPES =====

/**
 * Complete user information.
 * Mirrors: backend/app/schemas/usuario.py::UsuarioResponse
 */
export interface User {
  id: number;
  username: string;
  nombre: string;
  rol: Rol;
  primer_login: boolean;
  gemini_api_key_valid: boolean;
  activo: boolean;
  created_at: string; // ISO 8601 datetime string
  updated_at: string; // ISO 8601 datetime string
  last_login: string | null; // ISO 8601 datetime string or null
}

/**
 * Basic user information returned after login.
 * Mirrors: backend/app/schemas/auth.py::UserInfo
 */
export interface UserInfo {
  id: number;
  username: string;
  nombre: string;
  rol: Rol;
  primer_login: boolean;
  gemini_api_key_valid: boolean;
}

/**
 * Reduced user information for lists.
 * Mirrors: backend/app/schemas/usuario.py::UsuarioListItem
 */
export interface UserListItem {
  id: number;
  username: string;
  nombre: string;
  rol: Rol;
  activo: boolean;
  created_at: string;
  last_login: string | null;
}

/**
 * User creation request.
 * Mirrors: backend/app/schemas/usuario.py::UsuarioCreate
 */
export interface UserCreate {
  username: string;
  nombre: string;
  rol: Rol;
}

/**
 * User update request.
 * Mirrors: backend/app/schemas/usuario.py::UsuarioUpdate
 */
export interface UserUpdate {
  nombre?: string;
  rol?: Rol;
}

// ===== AUTHENTICATION TYPES =====

/**
 * Login request payload.
 * Mirrors: backend/app/schemas/auth.py::LoginRequest
 */
export interface LoginRequest {
  username: string;
  password: string;
}

/**
 * Login response with token and user info.
 * Mirrors: backend/app/schemas/auth.py::TokenResponse
 */
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

/**
 * Change password request payload.
 * Mirrors: backend/app/schemas/auth.py::ChangePasswordRequest
 */
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

/**
 * Change password response.
 * Mirrors: backend/app/schemas/auth.py::ChangePasswordResponse
 */
export interface ChangePasswordResponse {
  message: string;
}

// ===== API RESPONSE TYPES =====

/**
 * Generic successful API response wrapper.
 * Used when the backend returns data with additional metadata.
 *
 * @template T - The type of the data payload
 */
export interface ApiResponse<T> {
  data: T;
  message?: string;
  meta?: {
    page?: number;
    per_page?: number;
    total?: number;
    [key: string]: unknown;
  };
}

/**
 * API error response structure.
 * Standardized error format from FastAPI exception handlers.
 */
export interface ApiError {
  detail: string | ApiErrorDetail[];
  message?: string;
  status_code?: number;
}

/**
 * Detailed validation error (FastAPI ValidationError format).
 */
export interface ApiErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * Paginated list response.
 * Mirrors: backend/app/schemas/usuario.py::UsuarioList pattern
 *
 * @template T - The type of items in the list
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

// ===== UTILITY TYPES =====

/**
 * Type guard to check if a value is an ApiError.
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    ('detail' in error || 'message' in error)
  );
}

/**
 * Extract error message from various error formats.
 */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (typeof error.detail === 'string') {
      return error.detail;
    }
    if (Array.isArray(error.detail) && error.detail.length > 0) {
      return error.detail.map((e) => e.msg).join(', ');
    }
    if (error.message) {
      return error.message;
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'Ocurrió un error inesperado';
}

/**
 * Type guard to check if a user has a specific role.
 */
export function hasRole(user: User | UserInfo | null, role: Rol): boolean {
  return user?.rol === role;
}

/**
 * Type guard to check if a user has any of the specified roles.
 */
export function hasAnyRole(user: User | UserInfo | null, roles: Rol[]): boolean {
  return user ? roles.includes(user.rol) : false;
}

/**
 * Check if a user is an admin.
 */
export function isAdmin(user: User | UserInfo | null): boolean {
  return hasRole(user, ROL.ADMIN);
}

/**
 * Check if a user is a coordinator.
 */
export function isCoordinador(user: User | UserInfo | null): boolean {
  return hasRole(user, ROL.COORDINADOR);
}

/**
 * Check if a user is a tutor.
 */
export function isTutor(user: User | UserInfo | null): boolean {
  return hasRole(user, ROL.TUTOR);
}

// ===== ACTIVIDAD (AUDIT) TYPES =====
export type { Actividad, ActividadListResponse, TipoActividad } from './actividad';
export { TIPO_ACTIVIDAD } from './actividad';
