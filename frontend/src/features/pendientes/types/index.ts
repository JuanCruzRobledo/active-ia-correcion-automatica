export interface ComisionPendiente {
  id: number;
  nombre: string;
  codigo: string;
  groupId: number | null;
  espera: number;
  corregidos: number;
  sinEntrega: number;
  moodleGraderUrl: string | null;
}

export interface UnidadPendiente {
  id: number;
  titulo: string;
  subtitulo: string;
  cmid: number | null;
  espera: number;
  corregidos: number;
  sinEntrega: number;
  comisiones: ComisionPendiente[];
}

export interface MateriaPendiente {
  id: number;
  nombre: string;
  totalEspera: number;
  totalCorregidos: number;
  totalSinEntrega: number;
  unidades: UnidadPendiente[];
}

export interface MateriasPendientesResponse {
  materias: MateriaPendiente[];
}
