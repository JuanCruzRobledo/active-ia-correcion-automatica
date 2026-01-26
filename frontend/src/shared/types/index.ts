/**
 * Shared TypeScript types
 * Ref: docs/specs/06-MODELO-DATOS.md
 */

// User types
export type RolEnum = 'ADMIN' | 'COORDINADOR' | 'TUTOR';

export interface User {
  id: number;
  username: string;
  nombre: string;
  rol: RolEnum;
  primerLogin: boolean;
  geminiApiKeyValid: boolean;
  activo: boolean;
  createdAt: string;
  updatedAt: string;
}

// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface ApiError {
  detail: string;
  status: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// Auth types
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
  firstLogin: boolean;
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}
