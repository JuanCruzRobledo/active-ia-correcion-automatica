// Tipos de la config del cron de snapshots + disparo manual

export interface CronConfig {
  usuario_id: number | null;
  usuario_nombre: string | null;
  hora: number;
  minuto: number;
  activo: boolean;
}

export interface CronConfigUpdate {
  usuario_id: number | null;
  hora: number;
  minuto: number;
  activo: boolean;
}

export interface SnapshotResumen {
  id: number;
  materia_id: number;
  generado_en: string;
  total_alumnos: number;
  origen: string;
}

export interface MateriaConfigurada {
  materia_id: number;
  codigo: string;
  nombre: string;
  ultimo_snapshot: string | null;
  total_alumnos: number | null;
}
