import { useState } from 'react';
import { BookOpen, Plus, Search } from 'lucide-react';
import {
  useMaterias,
  useDeleteMateria,
  useRestoreMateria,
  useMateria,
} from '../hooks';
import type { MateriaListItem } from '../types';
import { MateriaForm } from '../components/MateriaForm';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Select } from '@/shared/components/ui/Select';
import { Badge } from '@/shared/components/ui/Badge';
import { Spinner } from '@/shared/components/ui/Spinner';
import { Table, type TableColumn } from '@/shared/components/ui/Table';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { Dropdown } from '@/shared/components/ui/Dropdown';
import { formatDate } from '@/shared/utils/date';

export const MateriasPage = () => {
  const [search, setSearch] = useState('');
  const [activaFilter, setActivaFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  // Build filters
  const filters = {
    search: search || undefined,
    activa: activaFilter === 'all' ? undefined : activaFilter === 'active',
    page,
    per_page: 20,
  };

  // Queries and mutations
  const { data, isLoading, error } = useMaterias(filters);
  const { data: editingMateria } = useMateria(editingId || 0);
  const deleteMutation = useDeleteMateria();
  const restoreMutation = useRestoreMateria();

  // Handlers
  const handleOpenCreate = () => {
    setEditingId(null);
    setShowForm(true);
  };

  const handleOpenEdit = (id: number) => {
    setEditingId(id);
    setShowForm(true);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingId(null);
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('¿Estás seguro de que deseas eliminar esta materia?')) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const handleRestore = async (id: number) => {
    await restoreMutation.mutateAsync(id);
  };

  // Table columns
  const columns: TableColumn<MateriaListItem>[] = [
    {
      key: 'codigo',
      header: 'Código',
      render: (materia) => (
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-1/10">
            <BookOpen className="h-4 w-4 text-accent-1" />
          </div>
          <div>
            <div className="font-medium text-foreground">{materia.codigo}</div>
            <div className="text-xs text-muted-foreground">{materia.nombre}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'num_coordinadores',
      header: 'Coordinadores',
      render: (materia) => (
        <span className="text-sm text-foreground">
          {materia.num_coordinadores}
        </span>
      ),
    },
    {
      key: 'num_comisiones',
      header: 'Comisiones',
      render: (materia) => (
        <span className="text-sm text-foreground">
          {materia.num_comisiones}
        </span>
      ),
    },
    {
      key: 'activa',
      header: 'Estado',
      render: (materia) => (
        <Badge variant={materia.activa ? 'success' : 'default'}>
          {materia.activa ? 'Activa' : 'Inactiva'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Fecha creación',
      render: (materia) => (
        <span className="text-sm text-muted-foreground">
          {formatDate(materia.created_at)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Acciones',
      className: 'text-right',
      sticky: true,
      render: (materia) => (
        <Dropdown
          trigger={
            <button className="text-gray-400 hover:text-gray-600 px-2 py-1 rounded hover:bg-gray-100">
              •••
            </button>
          }
          items={[
            {
              label: 'Editar',
              onClick: () => handleOpenEdit(materia.id),
              icon: '✏️',
            },
            materia.activa
              ? {
                  label: 'Eliminar',
                  onClick: () => handleDelete(materia.id),
                  icon: '🗑️',
                  variant: 'danger' as const,
                }
              : {
                  label: 'Restaurar',
                  onClick: () => handleRestore(materia.id),
                  icon: '↩️',
                },
          ]}
        />
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-danger bg-danger/10 p-4">
        <p className="text-sm text-danger">
          Error al cargar materias. Por favor, intenta nuevamente.
        </p>
      </div>
    );
  }

  const materias = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Materias</h1>
          <p className="text-sm text-muted-foreground">
            Gestión de materias y coordinadores
          </p>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Crear Materia
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="relative flex-1 md:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Buscar por código o nombre..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1); // Reset to first page on search
            }}
            className="pl-10"
          />
        </div>

        <div className="flex gap-2">
          <Select
            value={activaFilter}
            onChange={(e) => {
              setActivaFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">Todas</option>
            <option value="active">Activas</option>
            <option value="inactive">Inactivas</option>
          </Select>
        </div>
      </div>

      {/* Table */}
      {materias.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="h-12 w-12 text-muted-foreground" />}
          title="No hay materias"
          description="No se encontraron materias con los filtros aplicados"
          action={
            <Button onClick={handleOpenCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Crear primera materia
            </Button>
          }
        />
      ) : (
        <>
          <Table
            columns={columns}
            data={materias}
            keyExtractor={(materia) => materia.id}
          />

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border pt-4">
              <p className="text-sm text-muted-foreground">
                Mostrando {(page - 1) * 20 + 1} -{' '}
                {Math.min(page * 20, data?.total || 0)} de {data?.total || 0}{' '}
                materias
              </p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Anterior
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Create/Edit Modal */}
      <MateriaForm
        isOpen={showForm}
        onClose={handleCloseForm}
        materia={editingMateria || undefined}
      />
    </div>
  );
};
