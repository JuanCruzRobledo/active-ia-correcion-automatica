// Tipos del ABM de Cohortes/Cuatrimestres (Dashboard de Gestores)

export interface Cuatrimestre {
  id: number;
  cohorte_id: number;
  numero: number;
  nombre?: string | null;
}

export interface Cohorte {
  id: number;
  codigo: string;
  nombre?: string | null;
  activa: boolean;
  created_at: string;
  cuatrimestres: Cuatrimestre[];
}

export interface CohorteCreate {
  codigo: string;
  nombre?: string | null;
}

export interface CohorteUpdate {
  nombre?: string | null;
  activa?: boolean;
}

export interface CuatrimestreCreate {
  numero: number;
  nombre?: string | null;
}
