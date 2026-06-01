// Tipos de la feature "Por entregar" (correcciones pendientes de subir a Moodle).

export interface CorreccionPorEntrega {
  correccion_id: number;
  entrega_id: number;
  alumno_nombre: string;
  materia_id: number;
  materia_nombre: string;
  comision_id: number;
  comision_nombre: string;
  rubrica_id: number;
  rubrica_titulo: string;
  tipo_rubrica: string;
  nota: number;
  etiqueta_nota: string;
  requiere_comentario_tutor: boolean;
  estado_ultimo_intento: 'none' | 'error';
  mensaje_error: string | null;
  corregido_at: string | null;
}

export interface PorEntregarResponse {
  items: CorreccionPorEntrega[];
  total_pendientes: number;
  total_automaticas: number;
  total_requieren_comentario: number;
  no_vinculadas: number;
}

export interface EntregaErrorItem {
  alumno: string;
  motivo: string;
}

export interface EntregaMasivaResumen {
  enviadas: number;
  ya_enviadas: number;
  ya_calificadas_en_moodle: number;
  omitidas_requieren_comentario: number;
  errores: EntregaErrorItem[];
}
