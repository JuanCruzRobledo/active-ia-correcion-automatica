import { useState } from 'react';
import { GraduationCap, MoreVertical, Pencil, Plus, Trash2, X } from 'lucide-react';
import {
  Badge,
  Button,
  ConfirmDialog,
  Dropdown,
  EmptyState,
  HelpButton,
  LoadingState,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import {
  useAddCuatrimestre,
  useCohortes,
  useDeleteCohorte,
  useDeleteCuatrimestre,
} from '../hooks/useCohortes';
import { CohorteFormModal } from '../components/CohorteFormModal';
import type { Cohorte } from '../types';

export const CohortesPage = () => {
  const { data: cohortes, isLoading, error } = useCohortes();
  const deleteCohorte = useDeleteCohorte();
  const addCuatrimestre = useAddCuatrimestre();
  const deleteCuatrimestre = useDeleteCuatrimestre();

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editing, setEditing] = useState<Cohorte | null>(null);
  const [toDelete, setToDelete] = useState<Cohorte | null>(null);

  const handleCreate = () => {
    setEditing(null);
    setIsFormOpen(true);
  };

  const handleEdit = (cohorte: Cohorte) => {
    setEditing(cohorte);
    setIsFormOpen(true);
  };

  const handleConfirmDelete = () => {
    if (!toDelete) return;
    deleteCohorte.mutate(toDelete.id, {
      onSuccess: () => setToDelete(null),
    });
  };

  const handleAddCuatrimestre = (cohorte: Cohorte) => {
    const usados = cohorte.cuatrimestres.map((c) => c.numero);
    const siguiente = [1, 2, 3, 4].find((n) => !usados.includes(n));
    if (!siguiente) return;
    addCuatrimestre.mutate({ cohorteId: cohorte.id, data: { numero: siguiente } });
  };

  if (isLoading) return <LoadingState title="Cargando cohortes…" />;

  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-destructive mb-4">Error al cargar cohortes</div>
        <Button onClick={() => window.location.reload()}>Reintentar</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-foreground sm:text-3xl">Cohortes</h1>
            <HelpButton title="Ayuda — Cohortes" content={helpContent.cohortes} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Cohortes y cuatrimestres para el dashboard de gestores
          </p>
        </div>
        <Button onClick={handleCreate} className="w-full sm:w-auto">
          <Plus className="h-4 w-4" /> Nueva cohorte
        </Button>
      </div>

      {/* Lista */}
      {!cohortes || cohortes.length === 0 ? (
        <div className="rounded-lg border border-border bg-card">
          <EmptyState
            icon="🎓"
            title="No hay cohortes"
            description="Creá la primera cohorte (ej: M26) y agregale sus cuatrimestres."
            action={<Button onClick={handleCreate}>+ Crear cohorte</Button>}
          />
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {cohortes.map((cohorte) => {
            const completa = cohorte.cuatrimestres.length >= 4;
            return (
              <div
                key={cohorte.id}
                className="rounded-lg border border-border bg-card p-4 sm:p-6"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10">
                      <GraduationCap className="h-5 w-5 text-accent" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-lg font-semibold text-foreground">
                          {cohorte.codigo}
                        </span>
                        <Badge variant={cohorte.activa ? 'success' : 'default'}>
                          {cohorte.activa ? 'Activa' : 'Inactiva'}
                        </Badge>
                      </div>
                      {cohorte.nombre && (
                        <p className="truncate text-sm text-muted-foreground">{cohorte.nombre}</p>
                      )}
                    </div>
                  </div>
                  <Dropdown
                    align="right"
                    trigger={
                      <span
                        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:h-9 sm:w-9"
                        aria-label="Acciones de la cohorte"
                      >
                        <MoreVertical className="h-5 w-5" />
                      </span>
                    }
                    items={[
                      {
                        label: 'Editar',
                        icon: <Pencil className="h-4 w-4" />,
                        onClick: () => handleEdit(cohorte),
                      },
                      {
                        label: 'Eliminar',
                        icon: <Trash2 className="h-4 w-4" />,
                        variant: 'danger',
                        onClick: () => setToDelete(cohorte),
                      },
                    ]}
                  />
                </div>

                {/* Cuatrimestres */}
                <div className="mt-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Cuatrimestres
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {cohorte.cuatrimestres.length === 0 && (
                      <span className="text-sm text-muted-foreground">Sin cuatrimestres</span>
                    )}
                    {cohorte.cuatrimestres.map((cuatri) => (
                      <span
                        key={cuatri.id}
                        className="inline-flex items-center gap-1 rounded-full bg-muted py-1 pl-3 pr-1 text-sm text-foreground"
                      >
                        Cuatrimestre {cuatri.numero}
                        <button
                          onClick={() => deleteCuatrimestre.mutate(cuatri.id)}
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive touch-manipulation"
                          aria-label={`Quitar cuatrimestre ${cuatri.numero}`}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    ))}
                    {!completa && (
                      <button
                        onClick={() => handleAddCuatrimestre(cohorte)}
                        disabled={addCuatrimestre.isPending}
                        className="inline-flex items-center gap-1 rounded-full border border-dashed border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-accent hover:text-accent disabled:opacity-50 touch-manipulation"
                      >
                        <Plus className="h-3.5 w-3.5" /> Agregar
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {isFormOpen && (
        <CohorteFormModal onClose={() => setIsFormOpen(false)} cohorte={editing} />
      )}

      <ConfirmDialog
        isOpen={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Eliminar cohorte"
        message={
          toDelete
            ? `¿Seguro que querés eliminar la cohorte ${toDelete.codigo}? Esta acción no se puede deshacer.`
            : ''
        }
        confirmLabel="Eliminar"
        variant="destructive"
        isLoading={deleteCohorte.isPending}
      />
    </div>
  );
};
