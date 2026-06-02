import { apiClient } from '@/shared/services/api-client';
import type {
  AgruparPor,
  ConsultaGestion,
  CursoGestion,
  FiltrosDisponibles,
  FiltrosGestion,
} from '../types';

const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export async function getCursos(): Promise<CursoGestion[]> {
  const { data } = await apiClient.get<CursoGestion[]>('/gestion/cursos');
  return data;
}

export async function getFiltros(materiaId: number): Promise<FiltrosDisponibles> {
  const { data } = await apiClient.get<FiltrosDisponibles>(
    `/gestion/cursos/${materiaId}/filtros`
  );
  return data;
}

export async function consultarGestion(
  materiaId: number,
  filtros: FiltrosGestion
): Promise<ConsultaGestion> {
  const { data } = await apiClient.post<ConsultaGestion>(
    `/gestion/cursos/${materiaId}/consulta`,
    filtros
  );
  return data;
}

/**
 * Descarga el .xlsx (una hoja por regional). Pide el body como blob y dispara
 * la descarga en el navegador usando el filename que manda el backend.
 */
/** Dispara la descarga en el navegador a partir de una respuesta blob de axios. */
function dispararDescarga(resp: { data: BlobPart; headers: Record<string, unknown> }, fallback: string): void {
  const cd = resp.headers['content-disposition'] as string | undefined;
  const match = cd?.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? fallback;

  const blob = new Blob([resp.data], { type: XLSX_MIME });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function descargarExcel(
  materiaId: number,
  filtros: FiltrosGestion,
  agruparPor: AgruparPor = 'regional'
): Promise<void> {
  const resp = await apiClient.post(
    `/gestion/cursos/${materiaId}/excel?agrupar_por=${agruparPor}`,
    filtros,
    { responseType: 'blob' }
  );
  dispararDescarga(resp, 'gestion.xlsx');
}

export type PendientesPor = 'trabajo' | 'comision';

/** Excel de entregas pendientes de corregir del curso (por práctico o por comisión). */
export async function descargarPendientesExcel(
  materiaId: number,
  agruparPor: PendientesPor = 'trabajo'
): Promise<void> {
  const resp = await apiClient.get(
    `/gestion/cursos/${materiaId}/pendientes/excel?agrupar_por=${agruparPor}`,
    { responseType: 'blob' }
  );
  dispararDescarga(resp, 'pendientes.xlsx');
}
