import { useState } from 'react';
import { Pencil, Plus, Trash2, Users } from 'lucide-react';
import {
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  HelpButton,
  LoadingState,
  ResponsiveTable,
  type TableColumn,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import {
  useDeleteTutorNexo,
  useTutoresNexo,
} from '../hooks/useTutoresNexo';
import { TutorNexoFormModal } from '../components/TutorNexoFormModal';
import type { TutorNexo } from '../types';

export const TutoresNexoPage = () => {
  const { data: tutores, isLoading, error } = useTutoresNexo();
  const deleteTutor = useDeleteTutorNexo();

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editing, setEditing] = useState<TutorNexo | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TutorNexo | null>(null);

  const handleCreate = () => {
    setEditing(null);
    setIsFormOpen(true);
  };

  const handleEdit = (t: TutorNexo) => {
    setEditing(t);
    setIsFormOpen(true);
  };

  const handleConfirmDelete = () => {
    if (deleteTarget) {
      deleteTutor.mutate(deleteTarget.id, {
        onSuccess: () => setDeleteTarget(null),
      });
    }
  };

  if (isLoading) return <LoadingState title="Cargando tutores nexo…" />;

  if (error) {
    return (
      <div className="py-12 text-center">
        <div className="mb-4 text-destructive">Error al cargar tutores nexo</div>
        <Button onClick={() => window.location.reload()}>Reintentar</Button>
      </div>
    );
  }

  // Acciones de fila (reutilizadas por la tabla desktop y la card mobile).
  const renderActions = (t: TutorNexo) => (
    <div className="flex justify-end gap-2">
      <button
        onClick={() => handleEdit(t)}
        className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground touch-manipulation sm:min-h-9 sm:min-w-9"
        aria-label="Editar tutor nexo"
      >
        <Pencil className="h-4 w-4" />
      </button>
      <button
        onClick={() => setDeleteTarget(t)}
        className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive touch-manipulation sm:min-h-9 sm:min-w-9"
        aria-label="Eliminar tutor nexo"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );

  // Card mobile: misma informacion que la fila, apilada y tactil.
  const renderTutorCard = (t: TutorNexo) => (
    <div className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10">
            <Users className="h-5 w-5 text-accent" />
          </div>
          <div className="min-w-0">
            <div className="font-medium text-foreground truncate">{t.regional}</div>
            <div className="text-sm text-muted-foreground truncate">{t.nombre}</div>
          </div>
        </div>
        <div className="shrink-0">{renderActions(t)}</div>
      </div>

      <div className="text-sm text-muted-foreground break-all">{t.email}</div>

      <div>
        <Badge variant={t.activo ? 'success' : 'default'}>
          {t.activo ? 'Activo' : 'Inactivo'}
        </Badge>
      </div>
    </div>
  );

  const columns: TableColumn<TutorNexo>[] = [
    {
      key: 'regional',
      header: 'Regional',
      render: (t) => (
        <span className="inline-flex items-center gap-2 font-medium text-foreground">
          <Users className="h-4 w-4 text-accent" />
          {t.regional}
        </span>
      ),
    },
    {
      key: 'nombre',
      header: 'Nombre',
      render: (t) => <span className="text-foreground">{t.nombre}</span>,
    },
    {
      key: 'email',
      header: 'Email',
      render: (t) => <span className="text-muted-foreground break-all">{t.email}</span>,
    },
    {
      key: 'estado',
      header: 'Estado',
      render: (t) => (
        <Badge variant={t.activo ? 'success' : 'default'}>
          {t.activo ? 'Activo' : 'Inactivo'}
        </Badge>
      ),
    },
    {
      key: 'acciones',
      header: '',
      sticky: true,
      render: renderActions,
    },
  ];

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-foreground sm:text-3xl">Tutores Nexo</h1>
            <HelpButton title="Ayuda — Tutores Nexo" content={helpContent.tutoresNexo} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Reciben semanalmente el Excel de avance de los alumnos de su regional
          </p>
        </div>
        <Button onClick={handleCreate} className="w-full sm:w-auto">
          <Plus className="h-4 w-4" /> Nuevo tutor nexo
        </Button>
      </div>

      {/* Lista */}
      {!tutores || tutores.length === 0 ? (
        <div className="rounded-lg border border-border bg-card">
          <EmptyState
            icon="📨"
            title="No hay tutores nexo"
            description="Cargá un tutor nexo por regional para que reciba el Excel semanal."
            action={<Button onClick={handleCreate}>+ Crear tutor nexo</Button>}
          />
        </div>
      ) : (
        // El borde/fondo tipo "card" solo aplica en desktop (lg:), donde se
        // renderiza la <table>. En mobile, cada tarjeta de ResponsiveTable ya
        // trae su propio borde/fondo, asi que el wrapper queda transparente.
        <div className="lg:overflow-hidden lg:rounded-lg lg:border lg:border-border lg:bg-card">
          <ResponsiveTable
            columns={columns}
            data={tutores}
            keyExtractor={(item) => item.id}
            renderCard={renderTutorCard}
          />
        </div>
      )}

      {isFormOpen && (
        <TutorNexoFormModal onClose={() => setIsFormOpen(false)} tutorNexo={editing} />
      )}

      <ConfirmDialog
        isOpen={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        title="Eliminar tutor nexo"
        message={
          deleteTarget
            ? `¿Eliminar al tutor nexo de ${deleteTarget.regional} (${deleteTarget.nombre})? Esta acción no se puede deshacer.`
            : ''
        }
        confirmLabel="Eliminar"
        variant="destructive"
        isLoading={deleteTutor.isPending}
      />
    </div>
  );
};
