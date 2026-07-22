import { useState } from 'react';
import { AlertTriangle, ClipboardList, Users } from 'lucide-react';
import { HelpButton, LoadingState } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import {
  useConsultaGestion,
  useCursosGestion,
  useFiltrosGestion,
} from '../hooks/useGestion';
import {
  descargarExcel,
  descargarPendientesExcel,
  type PendientesPor,
} from '../services/gestion.service';
import { FiltrosGestionForm } from '../components/FiltrosGestionForm';
import { botonAccionCls } from '../components/botonAccion';
import { ResultadosGestionTable } from '../components/ResultadosGestionTable';
import {
  FILTROS_VACIOS,
  type AgruparPor,
  type ConsultaGestion,
  type FiltrosGestion,
} from '../types';

const SELECT_CLS =
  'w-full max-w-md min-h-11 rounded-md border border-border bg-card px-3 py-2 text-base text-foreground sm:min-h-0 sm:text-sm';

export function GestionPage() {
  const [materiaId, setMateriaId] = useState<number | null>(null);
  const [filtros, setFiltros] = useState<FiltrosGestion>(FILTROS_VACIOS);
  const [resultados, setResultados] = useState<ConsultaGestion | null>(null);
  const [descargando, setDescargando] = useState<AgruparPor | null>(null);
  const [descargandoPendientes, setDescargandoPendientes] = useState<PendientesPor | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const cursosQuery = useCursosGestion();
  const filtrosQuery = useFiltrosGestion(materiaId);
  const consulta = useConsultaGestion();

  // Mientras haya CUALQUIER operación en curso (o cargando filtros), se deshabilitan
  // todos los botones: evita disparar muchas consultas a Moodle en paralelo (se rompe).
  const ocupado =
    consulta.isPending ||
    descargando !== null ||
    descargandoPendientes !== null ||
    filtrosQuery.isFetching;

  const handleCursoChange = (id: number | null) => {
    setMateriaId(id);
    setFiltros(FILTROS_VACIOS);
    setResultados(null);
    setErrorMsg(null);
  };

  const handleConsultar = () => {
    if (materiaId == null) return;
    setErrorMsg(null);
    consulta.mutate(
      { materiaId, filtros },
      {
        onSuccess: setResultados,
        onError: () => setErrorMsg('No se pudo consultar. Revisá tus credenciales Moodle.'),
      }
    );
  };

  const handleDescargarPendientes = async (agruparPor: PendientesPor) => {
    if (materiaId == null) return;
    setDescargandoPendientes(agruparPor);
    setErrorMsg(null);
    try {
      await descargarPendientesExcel(materiaId, agruparPor);
    } catch {
      setErrorMsg('No se pudo generar el Excel de pendientes.');
    } finally {
      setDescargandoPendientes(null);
    }
  };

  const handleDescargar = async (agruparPor: AgruparPor) => {
    if (materiaId == null) return;
    setDescargando(agruparPor);
    setErrorMsg(null);
    try {
      await descargarExcel(materiaId, filtros, agruparPor);
    } catch {
      setErrorMsg('No se pudo generar el Excel.');
    } finally {
      setDescargando(null);
    }
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-start gap-3">
        <Users className="h-7 w-7 shrink-0 text-accent" />
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">Gestión</h1>
          <p className="text-sm text-muted-foreground">
            Filtrá usuarios de un curso de Moodle y descargá el Excel por regional.
          </p>
        </div>
        <div className="ml-auto shrink-0">
          <HelpButton title="Ayuda — Gestión" content={helpContent.gestion} label="Ayuda" />
        </div>
      </div>

      {/* Selector de curso */}
      <div>
        {/* UI-012: label asociada al select por htmlFor/id. */}
        <label htmlFor="gestion-curso" className="mb-1 block text-sm font-medium text-muted-foreground">Curso</label>
        {cursosQuery.isLoading ? (
          <LoadingState title="Cargando cursos…" />
        ) : cursosQuery.isError ? (
          // UI-004: el error del select de cursos ya no se descarta en silencio.
          <div className="flex items-center gap-2 rounded-md border border-border bg-card p-4 text-sm text-foreground">
            <AlertTriangle className="h-5 w-5 text-warning" />
            No se pudieron cargar los cursos. Verificá tus credenciales Moodle en tu perfil e
            intentá recargar la página.
          </div>
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <select
              id="gestion-curso"
              className={SELECT_CLS}
              value={materiaId ?? ''}
              onChange={(e) => handleCursoChange(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Elegí un curso…</option>
              {(cursosQuery.data ?? []).map((c) => (
                <option key={c.materia_id} value={c.materia_id}>
                  {c.nombre} ({c.codigo})
                </option>
              ))}
            </select>
            {materiaId != null && (
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <button
                  onClick={() => handleDescargarPendientes('trabajo')}
                  disabled={ocupado}
                  title="Entregas pendientes de corregir, una hoja por trabajo (resumen por práctico)"
                  className={botonAccionCls(descargandoPendientes === 'trabajo')}
                >
                  <ClipboardList className="h-4 w-4 shrink-0" />
                  {descargandoPendientes === 'trabajo' ? 'Generando…' : 'Pendientes por Práctico'}
                </button>
                <button
                  onClick={() => handleDescargarPendientes('comision')}
                  disabled={ocupado}
                  title="Entregas pendientes de corregir, una hoja por comisión (resumen por comisión)"
                  className={botonAccionCls(descargandoPendientes === 'comision')}
                >
                  <ClipboardList className="h-4 w-4 shrink-0" />
                  {descargandoPendientes === 'comision' ? 'Generando…' : 'Pendientes por Comisión'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filtros + resultados (solo con curso elegido) */}
      {materiaId != null && (
        <>
          {filtrosQuery.isLoading && (
            <LoadingState title="Cargando filtros del curso…" subtitle="Consultando Moodle." />
          )}

          {filtrosQuery.isError && (
            <div className="flex items-center gap-2 rounded-md border border-border bg-card p-4 text-sm text-foreground">
              <AlertTriangle className="h-5 w-5 text-warning" />
              No se pudieron cargar los filtros del curso. Verificá tus credenciales Moodle en tu
              perfil.
            </div>
          )}

          {filtrosQuery.data && (
            <FiltrosGestionForm
              opciones={filtrosQuery.data}
              filtros={filtros}
              onChange={setFiltros}
              onConsultar={handleConsultar}
              onDescargar={handleDescargar}
              consultando={consulta.isPending}
              descargando={descargando}
              bloqueado={ocupado}
            />
          )}

          {errorMsg && (
            <div className="flex items-center gap-2 rounded-md bg-warning/10 px-4 py-2 text-sm text-warning">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {errorMsg}
            </div>
          )}

          {resultados &&
            (resultados.total === 0 ? (
              <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
                Ningún alumno coincide con estos filtros.
              </div>
            ) : (
              <ResultadosGestionTable items={resultados.items} total={resultados.total} />
            ))}
        </>
      )}
    </div>
  );
}
