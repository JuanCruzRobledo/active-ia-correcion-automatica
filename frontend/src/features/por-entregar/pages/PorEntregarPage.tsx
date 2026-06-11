import { useNavigate } from 'react-router-dom';
import { Send, CheckCircle, Pencil, Info, RefreshCw, AlertTriangle } from 'lucide-react';
import { StatCard } from '@/features/dashboard/components/StatCard';
import { HelpButton, LoadingState } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { usePorEntregar } from '../hooks/usePorEntregar';
import { EntregarTodoButton } from '../components/EntregarTodoButton';
import { PorEntregarTable } from '../components/PorEntregarTable';

export function PorEntregarPage() {
  const navigate = useNavigate();
  const { data, isLoading, isFetching, refetch, error } = usePorEntregar();

  if (isLoading) {
    return <LoadingState title="Cargando…" subtitle="Buscando correcciones por entregar." />;
  }

  if (error) {
    return (
      <div className="space-y-6 p-4 sm:p-6">
        <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground sm:text-3xl">Por entregar</h1><HelpButton title="Ayuda — Por entregar" content={helpContent.porEntregar} /></div>
        <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-card p-8 text-center">
          <AlertTriangle className="h-10 w-10 text-warning" />
          <p className="font-semibold text-foreground">No se pudo cargar la lista</p>
          <button
            onClick={() => refetch()}
            className="flex cursor-pointer items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted touch-manipulation min-h-[44px]"
          >
            <RefreshCw className="h-4 w-4" />
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  const items = data?.items ?? [];
  const totalPendientes = data?.total_pendientes ?? 0;
  const totalAutomaticas = data?.total_automaticas ?? 0;
  const totalRequieren = data?.total_requieren_comentario ?? 0;
  const noVinculadas = data?.no_vinculadas ?? 0;

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground sm:text-3xl">Por entregar</h1><HelpButton title="Ayuda — Por entregar" content={helpContent.porEntregar} /></div>
          <p className="text-sm text-muted-foreground">
            Correcciones hechas en Active-IA que todavía no subiste a Moodle.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <EntregarTodoButton totalAutomaticas={totalAutomaticas} />
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 touch-manipulation min-h-[44px] sm:flex-none"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{isFetching ? 'Actualizando…' : 'Actualizar'}</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Pendientes de entregar"
          value={totalPendientes}
          subtitle="correcciones sin subir"
          icon={Send}
          variant={totalPendientes > 0 ? 'warning' : 'default'}
        />
        <StatCard
          title="Automáticas (TP)"
          value={totalAutomaticas}
          subtitle="suben con 'Entregar todo'"
          icon={CheckCircle}
          variant="success"
        />
        <StatCard
          title="Requieren comentario"
          value={totalRequieren}
          subtitle="subir a mano"
          icon={Pencil}
          variant="default"
        />
      </div>

      {noVinculadas > 0 && (
        <div className="flex items-center gap-2 rounded-md bg-muted/40 px-4 py-2 text-sm text-muted-foreground">
          <Info className="h-4 w-4 shrink-0" />
          <span>
            {noVinculadas} corrección(es) no vinculadas a Moodle (cargadas a mano o sin
            configuración Moodle) — no se pueden subir desde acá.
          </span>
        </div>
      )}

      {items.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <CheckCircle className="mx-auto h-10 w-10 text-success" />
          <p className="mt-3 font-semibold text-foreground">¡Todo entregado!</p>
          <p className="mt-1 text-sm text-muted-foreground">
            No tenés correcciones pendientes de subir a Moodle.
          </p>
          <button
            onClick={() => navigate('/pendientes')}
            className="mt-4 w-full cursor-pointer rounded-md border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted touch-manipulation min-h-[44px] sm:w-auto"
          >
            Ver pendientes por corregir
          </button>
        </div>
      ) : (
        <PorEntregarTable items={items} />
      )}
    </div>
  );
}
