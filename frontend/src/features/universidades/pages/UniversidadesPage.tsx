import { useState } from 'react';
import { Building2, MoreVertical, Pencil, Plus, Trash2 } from 'lucide-react';
import {
  Badge,
  Button,
  Checkbox,
  ConfirmDialog,
  Dropdown,
  LoadingState,
  Table,
} from '@/shared/components/ui';
import type { TableColumn } from '@/shared/components/ui';
import { useDeleteUniversidad, useUniversidades } from '../hooks';
import { UniversidadForm } from '../components/UniversidadForm';
import type { UniversidadListItem } from '../types';

/**
 * ABM de Universidades (Fase 5 multi-tenant). Sólo accesible para superadmin
 * (guard de ruta en `router.tsx`, entrada de menú en `navConfig.ts`).
 */
export const UniversidadesPage = () => {
  const [includeInactive, setIncludeInactive] = useState(false);
  const { data, isLoading } = useUniversidades({ includeInactive });
  const deleteMutation = useDeleteUniversidad();

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editing, setEditing] = useState<UniversidadListItem | null>(null);
  const [toDelete, setToDelete] = useState<UniversidadListItem | null>(null);

  const handleCreate = () => {
    setEditing(null);
    setIsFormOpen(true);
  };

  const handleEdit = (universidad: UniversidadListItem) => {
    setEditing(universidad);
    setIsFormOpen(true);
  };

  const handleConfirmDelete = () => {
    if (!toDelete) return;
    deleteMutation.mutate(toDelete.id, { onSuccess: () => setToDelete(null) });
  };

  const columns: TableColumn<UniversidadListItem>[] = [
    { key: 'nombre', header: 'Nombre' },
    {
      key: 'moodle_host',
      header: 'Campus',
      render: (u) => u.moodle_host || <span className="text-muted-foreground">Sin configurar</span>,
    },
    {
      key: 'activa',
      header: 'Estado',
      render: (u) => (
        <Badge variant={u.activa ? 'success' : 'default'}>{u.activa ? 'Activa' : 'Inactiva'}</Badge>
      ),
    },
    {
      key: 'acciones',
      header: 'Acciones',
      sticky: true,
      render: (u) => (
        <Dropdown
          align="right"
          trigger={
            <span
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:h-9 sm:w-9"
              aria-label="Acciones"
            >
              <MoreVertical className="h-5 w-5" />
            </span>
          }
          items={[
            { label: 'Editar', icon: <Pencil className="h-4 w-4" />, onClick: () => handleEdit(u) },
            {
              label: 'Dar de baja',
              icon: <Trash2 className="h-4 w-4" />,
              variant: 'danger',
              onClick: () => setToDelete(u),
              disabled: !u.activa,
            },
          ]}
        />
      ),
    },
  ];

  if (isLoading) return <LoadingState title="Cargando universidades…" />;

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Building2 className="h-6 w-6 text-muted-foreground" />
            <h1 className="text-2xl font-bold text-foreground sm:text-3xl">Universidades</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Administración de universidades (tenants). Sólo superadmin.
          </p>
        </div>
        <Button onClick={handleCreate} className="w-full sm:w-auto">
          <Plus className="h-4 w-4" /> Nueva universidad
        </Button>
      </div>

      <Checkbox
        label="Mostrar inactivas"
        checked={includeInactive}
        onChange={(e) => setIncludeInactive(e.target.checked)}
      />

      <div className="rounded-lg border border-border bg-card">
        <Table
          columns={columns}
          data={data?.items ?? []}
          keyExtractor={(u) => u.id}
          emptyMessage="No hay universidades para mostrar"
        />
      </div>

      {isFormOpen && (
        <UniversidadForm onClose={() => setIsFormOpen(false)} universidad={editing} />
      )}

      <ConfirmDialog
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Dar de baja universidad"
        message={
          toDelete
            ? `¿Seguro que querés dar de baja "${toDelete.nombre}"? Los usuarios con membresía en ella dejarán de poder operar. Las materias y comisiones asociadas NO se borran.`
            : ''
        }
        confirmLabel="Dar de baja"
        variant="destructive"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
};
