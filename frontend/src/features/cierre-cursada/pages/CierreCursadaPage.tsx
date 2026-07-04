import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileSpreadsheet } from 'lucide-react';
import { Button, EmptyState, Input, LoadingState, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { isAdmin, isCoordinador } from '@/shared/types';
import { materiasService } from '@/features/materias/services';
import { cohortesService } from '@/features/cohortes/services/cohortes.service';
import { ItemsMappingEditor } from '../components/ItemsMappingEditor';
import { HistorialRunsTable } from '../components/HistorialRunsTable';
import { cierreCursadaService } from '../services/cierre-cursada.service';
import { useCierreItems, useGenerarCierre, useHistorialCierre } from '../hooks/useCierreCursada';

/**
 * Cierre de cursada: elegir materia + cuatrimestre → revisar el mapeo de
 * ítems del calificador de Moodle (sugerido por regex, confirmable) → generar
 * el cierre (PROMOCIONA/REGULARIZA/RECURSA) → descargar el Excel. ADMIN y
 * COORDINADOR (solo materias que coordina — el backend igual lo valida).
 */
export const CierreCursadaPage = () => {
  const { user } = useAuth();
  const puedeEscribir = isAdmin(user) || isCoordinador(user);

  const [materiaId, setMateriaId] = useState<number | null>(null);
  const [cuatrimestreId, setCuatrimestreId] = useState<number | null>(null);
  const [umbralTp, setUmbralTp] = useState('100');

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

  const itemsQuery = useCierreItems(materiaId ?? 0, cuatrimestreId ?? 0);
  const generar = useGenerarCierre(materiaId ?? 0);
  const historial = useHistorialCierre(materiaId ?? 0);

  const umbralValido = umbralTp !== '' && Number(umbralTp) >= 0 && Number(umbralTp) <= 100;

  const handleGenerar = async () => {
    if (!cuatrimestreId || !umbralValido) return;
    const run = await generar.mutateAsync({
      cuatrimestre_id: cuatrimestreId,
      umbral_tp_pct: Number(umbralTp),
    });
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
          <h2 className="text-lg font-semibold text-foreground">Mapeo de ítems del calificador</h2>
          {itemsQuery.isLoading && <LoadingState title="Cargando ítems del calificador…" />}
          {itemsQuery.error && (
            <p className="text-sm text-destructive">
              No se pudo traer el calificador (¿credenciales de Moodle en tu perfil?).
            </p>
          )}
          {itemsQuery.data && (
            <ItemsMappingEditor
              materiaId={materiaId}
              cuatrimestreId={cuatrimestreId}
              items={itemsQuery.data}
            />
          )}

          <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/30 p-4 sm:flex-row sm:items-end sm:gap-4">
            <Input
              label="% mínimo de TPs aprobados"
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              value={umbralTp}
              onChange={(e) => setUmbralTp(e.target.value)}
              helperText="0 = no exigir ningún TP aprobado"
              error={!umbralValido ? 'Tiene que ser un número entre 0 y 100' : undefined}
              className="w-full sm:w-48"
            />
            <Button onClick={handleGenerar} isLoading={generar.isPending} disabled={!umbralValido}>
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
