// features/usuarios/types/index.ts
/**
 * TypeScript types for Usuarios feature.
 * 
 * Mirrors backend schemas from app/schemas/usuario.py
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
 */

export type RolEnum = 'ADMIN' | 'COORDINADOR' | 'TUTOR';

export interface Usuario {
  id: number;
  username: string;
  nombre: string;
  rol: RolEnum;
  primer_login: boolean;
  gemini_api_key_valid: boolean;
  activo: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

export interface UsuarioListItem {
  id: number;
  username: string;
  nombre: string;
  rol: RolEnum;
  activo: boolean;
  created_at: string;
  last_login: string | null;
}

export interface UsuarioList {
  items: UsuarioListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface UsuarioCreate {
  username: string;
  nombre: string;
  rol: RolEnum;
}

export interface UsuarioUpdate {
  nombre?: string;
  rol?: RolEnum;
}

export interface UsuarioCreateResponse {
  usuario: Usuario;
  password_temporal: string;
}

export interface ResetPasswordResponse {
  message: string;
  password_temporal: string;
}

export interface UsuariosFilters {
  rol?: RolEnum | 'TODOS';
  activo?: boolean | 'TODOS';
  search?: string;
  page?: number;
  per_page?: number;
}
