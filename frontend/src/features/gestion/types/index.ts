// Tipos de la feature "Gestión" (rol GESTOR) — espejo de app/schemas/gestion.py.

export interface CursoGestion {
  materia_id: number;
  nombre: string;
  codigo: string;
  moodle_course_id: number;
}

export interface OpcionCatalogo {
  value: string;
  label: string;
}

export interface FiltrosDisponibles {
  regionales: string[];
  comisiones: string[];
  roles: OpcionCatalogo[];
  estatus: OpcionCatalogo[];
  inactividad: OpcionCatalogo[];
}

export interface FiltrosGestion {
  rol?: string | null;
  estatus?: string | null;
  regionales: string[];
  comisiones: string[];
  inactividad_tipo?: string | null;
  inactividad_desde?: number | null;
  inactividad_hasta?: number | null;
}

export interface AlumnoGestion {
  nombre: string;
  apellido: string;
  email: string;
  regional: string;
  comision: string;
  dias_inactividad: number | null;
  tiempo_inactividad: string;
  suspendido: boolean;
}

export interface ConsultaGestion {
  items: AlumnoGestion[];
  total: number;
}

export const FILTROS_VACIOS: FiltrosGestion = {
  rol: null,
  estatus: null,
  regionales: [],
  comisiones: [],
  inactividad_tipo: null,
  inactividad_desde: null,
  inactividad_hasta: null,
};
