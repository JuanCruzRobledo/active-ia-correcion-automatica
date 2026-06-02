import { apiClient } from '@/shared/services/api-client';
import type {
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
export async function descargarExcel(
  materiaId: number,
  filtros: FiltrosGestion
): Promise<void> {
  const resp = await apiClient.post(
    `/gestion/cursos/${materiaId}/excel`,
    filtros,
    { responseType: 'blob' }
  );

  const cd = resp.headers['content-disposition'] as string | undefined;
  const match = cd?.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? 'gestion.xlsx';

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
