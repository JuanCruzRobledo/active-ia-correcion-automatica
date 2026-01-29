/**
 * Dashboard types - TypeScript interfaces for dashboard data.
 *
 * Ref: backend/app/schemas/dashboard.py
 */

// Admin Dashboard Types
export interface AdminStats {
  materias: number;
  comisiones: number;
  usuarios: number;
  rubricas: number;
}

// Coordinador Dashboard Types
export interface CorrectionProgress {
  id: number;
  comision: string;
  tutor: string;
  completed: number;
  total: number;
  last_activity: string | null;
}

export interface CoordinadorStats {
  comisiones: number;
  rubricas: number;
  pendientes: number;
  corrections_progress: CorrectionProgress[];
}

// Tutor Dashboard Types
export interface ComisionDetail {
  id: number;
  nombre: string;
  comision: string;
  alumnos: number;
  pendientes: number;
}

export interface TutorStats {
  comisiones: number;
  pendientes: number;
  corregidas: number;
  comisiones_details: ComisionDetail[];
}
