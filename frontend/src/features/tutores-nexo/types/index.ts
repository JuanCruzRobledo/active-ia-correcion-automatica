// Tipos del ABM de Tutores Nexo (notificaciones por email)

export interface TutorNexo {
  id: number;
  nombre: string;
  email: string;
  regional: string;
  activo: boolean;
  created_at: string;
}

export interface TutorNexoCreate {
  nombre: string;
  email: string;
  regional: string;
}

export interface TutorNexoUpdate {
  nombre?: string;
  email?: string;
  regional?: string;
  activo?: boolean;
}
