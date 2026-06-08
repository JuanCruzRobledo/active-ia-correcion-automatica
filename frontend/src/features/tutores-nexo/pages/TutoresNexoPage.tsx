import { useState } from 'react';
import { Pencil, Plus, Trash2, Users } from 'lucide-react';
import {
  Badge,
  Button,
  EmptyState,
  HelpButton,
  LoadingState,
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

  const handleCreate = () => {
    setEditing(null);
    setIsFormOpen(true);
  };

  const handleEdit = (t: TutorNexo) => {
    setEditing(t);
    setIsFormOpen(true);
  };

  const handleDelete = (t: TutorNexo) => {
    if (window.confirm(`¿Eliminar al tutor nexo de ${t.regional} (${t.nombre})?`)) {
      deleteTutor.mutate(t.id);
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-foreground">Tutores Nexo</h1>
            <HelpButton title="Ayuda — Tutores Nexo" content={helpContent.tutoresNexo} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Reciben semanalmente el Excel de avance de los alumnos de su regional
          </p>
        </div>
        <Button onClick={handleCreate}>
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
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Regional</th>
                <th className="px-4 py-3 text-left">Nombre</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {tutores.map((t) => (
                <tr key={t.id} className="transition-colors hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium text-foreground">
                    <span className="inline-flex items-center gap-2">
                      <Users className="h-4 w-4 text-accent" />
                      {t.regional}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-foreground">{t.nombre}</td>
                  <td className="px-4 py-3 text-muted-foreground">{t.email}</td>
                  <td className="px-4 py-3">
                    <Badge variant={t.activo ? 'success' : 'default'}>
                      {t.activo ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => handleEdit(t)}
                        className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                        aria-label="Editar tutor nexo"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(t)}
                        className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        aria-label="Eliminar tutor nexo"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isFormOpen && (
        <TutorNexoFormModal onClose={() => setIsFormOpen(false)} tutorNexo={editing} />
      )}
    </div>
  );
};
