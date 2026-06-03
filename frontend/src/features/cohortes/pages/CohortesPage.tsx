import { useState } from 'react';
import { GraduationCap, Pencil, Plus, Trash2, X } from 'lucide-react';
import {
  Badge,
  Button,
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

  const handleCreate = () => {
    setEditing(null);
    setIsFormOpen(true);
  };

  const handleEdit = (cohorte: Cohorte) => {
    setEditing(cohorte);
    setIsFormOpen(true);
  };

  const handleDeleteCohorte = (cohorte: Cohorte) => {
    if (window.confirm(`¿Eliminar la cohorte ${cohorte.codigo}?`)) {
      deleteCohorte.mutate(cohorte.id);
    }
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-foreground">Cohortes</h1>
            <HelpButton title="Ayuda — Cohortes" content={helpContent.cohortes} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Cohortes y cuatrimestres para el dashboard de gestores
          </p>
        </div>
        <Button onClick={handleCreate}>
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
                className="rounded-lg border border-border bg-card p-6"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                      <GraduationCap className="h-5 w-5 text-accent" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold text-foreground">
                          {cohorte.codigo}
                        </span>
                        <Badge variant={cohorte.activa ? 'success' : 'default'}>
                          {cohorte.activa ? 'Activa' : 'Inactiva'}
                        </Badge>
                      </div>
                      {cohorte.nombre && (
                        <p className="text-sm text-muted-foreground">{cohorte.nombre}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleEdit(cohorte)}
                      className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      aria-label="Editar cohorte"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteCohorte(cohorte)}
                      className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      aria-label="Eliminar cohorte"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
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
                        className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-sm text-foreground"
                      >
                        Cuatrimestre {cuatri.numero}
                        <button
                          onClick={() => deleteCuatrimestre.mutate(cuatri.id)}
                          className="text-muted-foreground transition-colors hover:text-destructive"
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
                        className="inline-flex items-center gap-1 rounded-full border border-dashed border-border px-3 py-1 text-sm text-muted-foreground transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
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
    </div>
  );
};
