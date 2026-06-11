import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, CheckCircle, Users, RefreshCw, AlertTriangle } from 'lucide-react';
import { StatCard } from '@/features/dashboard/components/StatCard';
import { HelpButton, LoadingState } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { MateriaBlock } from '../components';
import { ImportarButton } from '../components/ImportarButton';
import { usePendientesMoodle } from '../hooks/usePendientesMoodle';

export function PendientesPage() {
  const [showUrgentOnly, setShowUrgentOnly] = useState(false);
  const navigate = useNavigate();
  const { data, isLoading, isRefreshing, refresh, error } = usePendientesMoodle();

  if (isLoading) {
    return (
      <LoadingState
        title="Cargando pendientes…"
        subtitle="Consultando Moodle, puede tardar unos segundos."
      />
    );
  }

  const is424 =
    error &&
    'response' in (error as any) &&
    (error as any).response?.status === 424;

  if (error) {
    return (
      <div className="space-y-4 p-4 sm:space-y-6 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground sm:text-3xl">Pendientes Moodle</h1><HelpButton title="Ayuda — Pendientes" content={helpContent.pendientes} /></div>
          {!is424 && (
            <button
              onClick={refresh}
              disabled={isRefreshing}
              className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              {isRefreshing ? 'Actualizando…' : 'Actualizar'}
            </button>
          )}
        </div>
        <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-card p-8 text-center">
          <AlertTriangle className="h-10 w-10 text-warning" />
          <div>
            <p className="font-semibold text-foreground">
              {is424
                ? 'Credenciales Moodle no configuradas'
                : 'Error conectando a Moodle'}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {is424
                ? 'Configurá tus credenciales Moodle en tu perfil para ver los pendientes.'
                : 'Moodle no está disponible en este momento. Intentá más tarde.'}
            </p>
          </div>
          {is424 ? (
            <button
              onClick={() => navigate('/perfil')}
              className="min-h-11 w-full cursor-pointer rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 sm:w-auto"
            >
              Ir a mi perfil
            </button>
          ) : (
            <button
              onClick={refresh}
              disabled={isRefreshing}
              className="flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              {isRefreshing ? 'Actualizando…' : 'Reintentar'}
            </button>
          )}
        </div>
      </div>
    );
  }

  const materias = data?.materias ?? [];
  const totalEspera = materias.reduce((acc, m) => acc + m.totalEspera, 0);
  const totalCorregidos = materias.reduce((acc, m) => acc + m.totalCorregidos, 0);
  const totalSinEntrega = materias.reduce((acc, m) => acc + m.totalSinEntrega, 0);

  const filteredMaterias = showUrgentOnly
    ? materias.filter((m) => m.totalEspera > 0)
    : materias;

  return (
    <div className="space-y-4 p-4 sm:space-y-6 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground sm:text-3xl">Pendientes Moodle</h1><HelpButton title="Ayuda — Pendientes" content={helpContent.pendientes} /></div>
        <div className="flex items-center gap-2">
          {totalEspera > 0 && (
            <ImportarButton
              scope="tutor"
              label="Importar todo"
              modalTitle="Importar todas mis pendientes"
              fullWidth
            />
          )}
          <button
            onClick={refresh}
            disabled={isRefreshing}
            aria-label="Actualizar"
            className="flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{isRefreshing ? 'Actualizando…' : 'Actualizar'}</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Esperando corrección"
          value={totalEspera}
          subtitle="entregas pendientes"
          icon={Clock}
          variant={totalEspera > 0 ? 'destructive' : 'default'}
        />
        <StatCard
          title="Corregidos"
          value={totalCorregidos}
          subtitle="entregas revisadas"
          icon={CheckCircle}
          variant="success"
        />
        <StatCard
          title="Sin entrega"
          value={totalSinEntrega}
          subtitle="alumnos sin entregar"
          icon={Users}
          variant="default"
        />
      </div>

      <div className="inline-flex w-full rounded-full bg-muted p-1 sm:w-auto">
        <button
          onClick={() => setShowUrgentOnly(false)}
          className={`min-h-11 flex-1 cursor-pointer rounded-full px-4 py-1.5 text-sm font-medium transition-colors sm:flex-none ${
            !showUrgentOnly
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-muted/80'
          }`}
        >
          Todos
        </button>
        <button
          onClick={() => setShowUrgentOnly(true)}
          className={`min-h-11 flex-1 cursor-pointer rounded-full px-4 py-1.5 text-sm font-medium transition-colors sm:flex-none ${
            showUrgentOnly
              ? 'bg-destructive text-destructive-foreground'
              : 'text-muted-foreground hover:bg-muted/80'
          }`}
        >
          Solo con pendientes
        </button>
      </div>

      {filteredMaterias.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <CheckCircle className="mx-auto h-10 w-10 text-success" />
          <p className="mt-3 font-semibold text-foreground">¡Todo al día!</p>
          <p className="mt-1 text-sm text-muted-foreground">
            No hay entregas pendientes de corrección.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredMaterias.map((m) => (
            <MateriaBlock key={m.id} materia={m} showUrgentOnly={showUrgentOnly} />
          ))}
        </div>
      )}
    </div>
  );
}
