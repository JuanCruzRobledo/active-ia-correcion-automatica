// Tipos de la feature de notificaciones por email

export type TipoNotificacion = 'ALUMNO' | 'TUTOR_ACADEMICO' | 'TUTOR_NEXO';
export type EstadoEnvio = 'PENDIENTE' | 'ENVIADO' | 'ERROR' | 'OMITIDO';

export interface NotifCronConfig {
  usuario_id: number | null;
  usuario_nombre: string | null;
  dia_semana: number; // 0=lunes … 6=domingo
  hora: number;
  minuto: number;
  activo: boolean;
  remitente: string | null;
}

export interface NotifCronConfigUpdate {
  usuario_id: number | null;
  dia_semana: number;
  hora: number;
  minuto: number;
  activo: boolean;
  remitente: string | null;
}

export interface EnvioEmailLog {
  id: number;
  tanda_id: string;
  tipo: TipoNotificacion;
  destinatario_email: string;
  destinatario_ref: string | null;
  asunto: string | null;
  estado: EstadoEnvio;
  resend_id: string | null;
  error: string | null;
  intentos: number;
  created_at: string;
  enviado_en: string | null;
}

export interface CorridaResumen {
  tanda_id: string;
  alumnos: number;
  tutores: number;
  nexos: number;
}
