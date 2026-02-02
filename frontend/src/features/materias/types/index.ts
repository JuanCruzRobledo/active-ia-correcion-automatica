// Materia types for Active-IA frontend

export interface Materia {
  id: number;
  codigo: string;
  nombre: string;
  descripcion: string | null;
  activa: boolean;
  created_at: string;
  updated_at: string;
}

export interface CoordinadorInfo {
  id: number;
  username: string;
  nombre: string;
  asignado_en: string;
}

export interface MateriaDetail extends Materia {
  coordinadores: CoordinadorInfo[];
}

export interface MateriaListItem {
  id: number;
  codigo: string;
  nombre: string;
  activa: boolean;
  created_at: string;
  num_coordinadores: number;
  num_comisiones: number;
}

export interface MateriaList {
  items: MateriaListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface MateriaCreate {
  codigo: string;
  nombre: string;
  descripcion?: string;
  coordinador_ids?: number[];
}

export interface MateriaUpdate {
  nombre?: string;
  descripcion?: string;
  coordinador_ids?: number[];
}

export interface MateriasFilters {
  activa?: boolean;
  search?: string;
  page?: number;
  per_page?: number;
}

export interface CoordinadoresAssign {
  coordinador_ids: number[];
}

export interface CoordinadoresResponse {
  materia_id: number;
  coordinadores: Array<{
    id: number;
    username: string;
    nombre: string;
  }>;
  message: string;
}
