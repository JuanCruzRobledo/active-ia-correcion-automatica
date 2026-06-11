import { useState } from 'react';
import { FileSpreadsheet } from 'lucide-react';
import {
  Button,
  HelpButton,
  LoadingState,
  Select,
  Spinner,
} from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { useArbol, useAvance, useDescargarExcel } from '../hooks/useDashboardGestor';
import { EstadoPie } from '../components/EstadoPie';
import { DetalleModal } from '../components/DetalleModal';
import type { EstadoAvance } from '../types';
import { formatFechaHoraArg } from '@/shared/utils/fecha';

const fmtFecha = (iso: string | null) => (iso ? formatFechaHoraArg(iso) : null);

export const DashboardGestorPage = () => {
  const { data: arbol, isLoading: loadingArbol } = useArbol();

  const [cohorteId, setCohorteId] = useState<number | null>(null);
  const [cuatrimestreId, setCuatrimestreId] = useState<number | null>(null);
  const [materiaId, setMateriaId] = useState<number | null>(null);
  const [estadoModal, setEstadoModal] = useState<EstadoAvance | null>(null);

  const { data: avance, isFetching: fetchingAvance } = useAvance(cuatrimestreId, materiaId);
  const descargarExcel = useDescargarExcel();

  const cohorteSel = arbol?.find((c) => c.id === cohorteId) ?? null;
  const cuatriSel = cohorteSel?.cuatrimestres.find((q) => q.id === cuatrimestreId) ?? null;

  const cohorteOptions: SelectOption[] = [
    { value: '', label: 'Elegí una cohorte' },
    ...(arbol ?? []).map((c) => ({ value: String(c.id), label: c.codigo })),
  ];
  const cuatriOptions: SelectOption[] = [
    { value: '', label: 'Elegí un cuatrimestre' },
    ...(cohorteSel?.cuatrimestres ?? []).map((q) => ({
      value: String(q.id),
      label: `Cuatrimestre ${q.numero}`,
    })),
  ];
  const materiaOptions: SelectOption[] = [
    { value: '', label: 'Todas las materias' },
    ...(cuatriSel?.materias ?? []).map((m) => ({ value: String(m.id), label: m.nombre })),
  ];

  const handleCohorte = (v: string) => {
    setCohorteId(v ? Number(v) : null);
    setCuatrimestreId(null);
    setMateriaId(null);
  };
  const handleCuatri = (v: string) => {
    setCuatrimestreId(v ? Number(v) : null);
    setMateriaId(null);
  };

  if (loadingArbol) return <LoadingState title="Cargando dashboard…" />;

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">Avance académico</h1>
        <HelpButton title="Ayuda — Avance académico" content={helpContent.dashboardGestor} />
      </div>

      {/* Selectores */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Select label="Cohorte" options={cohorteOptions} value={cohorteId ? String(cohorteId) : ''} onChange={(e) => handleCohorte(e.target.value)} />
          <Select label="Cuatrimestre" options={cuatriOptions} value={cuatrimestreId ? String(cuatrimestreId) : ''} onChange={(e) => handleCuatri(e.target.value)} disabled={!cohorteSel} />
          <Select label="Materia" options={materiaOptions} value={materiaId ? String(materiaId) : ''} onChange={(e) => setMateriaId(e.target.value ? Number(e.target.value) : null)} disabled={!cuatriSel} />
        </div>
      </div>

      {/* Gráfico */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        {cuatrimestreId == null ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            Elegí una cohorte y un cuatrimestre para ver el avance.
          </p>
        ) : fetchingAvance ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <Spinner /> Cargando avance…
          </div>
        ) : avance ? (
          <>
            <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <h2 className="min-w-0 break-words text-lg font-semibold text-foreground">
                {avance.titulo}
              </h2>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                <span className="text-sm text-muted-foreground">
                  {avance.total} alumno(s)
                  {avance.generado_en && ` · actualizado ${fmtFecha(avance.generado_en)}`}
                </span>
                {avance.total > 0 && cuatrimestreId != null && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full sm:w-auto"
                    isLoading={descargarExcel.isPending}
                    onClick={() =>
                      descargarExcel.mutate({ cuatrimestreId, materiaId })
                    }
                  >
                    <FileSpreadsheet className="h-4 w-4" /> Excel
                  </Button>
                )}
              </div>
            </div>
            {avance.total === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No hay datos todavía. Generá un snapshot desde <strong className="text-foreground">Snapshots</strong> (admin).
              </p>
            ) : (
              <>
                <EstadoPie conteos={avance.conteos} onSlice={setEstadoModal} />
                <p className="mt-2 text-center text-xs text-muted-foreground">
                  Hacé clic en una porción para ver el detalle de esos alumnos.
                </p>
              </>
            )}
          </>
        ) : null}
      </div>

      {/* Modal de detalle */}
      {estadoModal && (
        <DetalleModal
          cuatrimestreId={cuatrimestreId}
          materiaId={materiaId}
          estado={estadoModal}
          onClose={() => setEstadoModal(null)}
        />
      )}
    </div>
  );
};
