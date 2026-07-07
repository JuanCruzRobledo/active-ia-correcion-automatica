import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileSpreadsheet } from 'lucide-react';
import { Button, EmptyState, LoadingState, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { isAdmin, isCoordinador } from '@/shared/types';
import { materiasService } from '@/features/materias/services';
import { cohortesService } from '@/features/cohortes/services/cohortes.service';
import { HistorialRunsTable } from '../components/HistorialRunsTable';
import { cierreCursadaService } from '../services/cierre-cursada.service';
import { useGenerarCierre, useHistorialCierre } from '../hooks/useCierreCursada';

/**
 * Cierre de cursada: elegir materia + cuatrimestre → generar el cierre
 * (PROMOCIONA/REGULARIZA/RECURSA) → descargar el Excel. ADMIN y
 * COORDINADOR (solo materias que coordina — el backend igual lo valida).
 */
export const CierreCursadaPage = () => {
  const { user } = useAuth();
  const puedeEscribir = isAdmin(user) || isCoordinador(user);

  const [materiaId, setMateriaId] = useState<number | null>(null);
  const [cuatrimestreId, setCuatrimestreId] = useState<number | null>(null);

  const { data: materias, isLoading: cargandoMaterias } = useQuery({
    queryKey: ['materias', 'activas'],
    queryFn: () => materiasService.getAll({ activa: true, per_page: 100 }),
  });
  const { data: cohortes, isLoading: cargandoCohortes } = useQuery({
    queryKey: ['cohortes'],
    queryFn: () => cohortesService.getAll(),
  });

  const materiaOptions: SelectOption[] = useMemo(
    () => (materias?.items ?? []).map((m) => ({ value: String(m.id), label: `${m.codigo} — ${m.nombre}` })),
    [materias]
  );
  const cuatrimestreOptions: SelectOption[] = useMemo(
    () =>
      (cohortes ?? []).flatMap((c) =>
        c.cuatrimestres.map((cu) => ({
          value: String(cu.id),
          label: `${c.codigo} — ${cu.nombre || `Cuatrimestre ${cu.numero}`}`,
        }))
      ),
    [cohortes]
  );

  const generar = useGenerarCierre(materiaId ?? 0);
  const historial = useHistorialCierre(materiaId ?? 0);

  const handleGenerar = async () => {
    if (!cuatrimestreId) return;
    const run = await generar.mutateAsync({ cuatrimestre_id: cuatrimestreId });
    await cierreCursadaService.descargarExcel(run.id);
  };

  if (!puedeEscribir) {
    return (
      <EmptyState
        icon="🔒"
        title="Sin acceso"
        description="Esta pantalla es para ADMIN o coordinadores de la materia."
      />
    );
  }

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Cierre de cursada</h1>
        <p className="text-sm text-muted-foreground">
          Calcula quién PROMOCIONA, quién REGULARIZA y quién RECURSA a partir del calificador
          de Moodle.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Select
          label="Materia"
          placeholder="Elegí una materia"
          options={materiaOptions}
          value={materiaId != null ? String(materiaId) : ''}
          onChange={(e) => setMateriaId(e.target.value ? Number(e.target.value) : null)}
          disabled={cargandoMaterias}
        />
        <Select
          label="Cuatrimestre"
          placeholder="Elegí un cuatrimestre"
          options={cuatrimestreOptions}
          value={cuatrimestreId != null ? String(cuatrimestreId) : ''}
          onChange={(e) => setCuatrimestreId(e.target.value ? Number(e.target.value) : null)}
          disabled={cargandoCohortes}
        />
      </div>

      {materiaId && cuatrimestreId && (
        <div className="space-y-4">
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/30 p-4 sm:flex-row sm:items-end sm:gap-4">
            <Button onClick={handleGenerar} isLoading={generar.isPending}>
              <FileSpreadsheet className="mr-1 h-4 w-4" />
              Generar cierre y descargar Excel
            </Button>
          </div>

          <h2 className="text-lg font-semibold text-foreground">Historial de corridas</h2>
          {historial.isLoading && <LoadingState title="Cargando historial…" />}
          {historial.data && <HistorialRunsTable runs={historial.data} />}
        </div>
      )}
    </div>
  );
};
