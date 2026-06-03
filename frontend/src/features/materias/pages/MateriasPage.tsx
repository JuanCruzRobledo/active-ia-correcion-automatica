import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, Pencil, Trash2, RotateCcw } from 'lucide-react';
import {
  useMaterias,
  useDeleteMateria,
  useRestoreMateria,
  useMateria,
} from '../hooks';
import { MateriaForm } from '../components/MateriaForm';
import type { MateriaListItem, MateriasFilters } from '../types';
import {
  Button,
  Input,
  Select,
  Badge,
  Table,
  LoadingState,
  HelpButton,
  EmptyState,
  Dropdown,
  type TableColumn,
  type SelectOption,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { formatDate } from '@/shared/utils';

interface MateriaPageFilters {
  activa: 'TODOS' | 'true' | 'false';
  search: string;
  page: number;
  per_page: number;
}

export const MateriasPage = () => {
  const [inputSearch, setInputSearch] = useState('');
  const [filters, setFilters] = useState<MateriaPageFilters>({
    activa: 'TODOS',
    search: '',
    page: 1,
    per_page: 20,
  });
  const isFirstRender = useRef(true);
  const navigate = useNavigate();

  // Debounce: actualiza el filtro 400ms después de que el usuario deja de escribir
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const timer = setTimeout(() => {
      setFilters((prev) => ({ ...prev, search: inputSearch, page: 1 }));
    }, 400);
    return () => clearTimeout(timer);
  }, [inputSearch]);

  // Modal state
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  // Derive API-compatible filters from page state
  const apiFilters: MateriasFilters = {
    search: filters.search || undefined,
    activa: filters.activa === 'TODOS' ? undefined : filters.activa === 'true',
    page: filters.page,
    per_page: filters.per_page,
  };

  const { data, isLoading, error } = useMaterias(apiFilters);
  const { data: editingMateria } = useMateria(editingId || 0);
  const deleteMutation = useDeleteMateria();
  const restoreMutation = useRestoreMateria();

  // Modal handlers
  const handleCreate = () => {
    setEditingId(null);
    setIsFormOpen(true);
  };

  const handleEdit = (id: number) => {
    setEditingId(id);
    setIsFormOpen(true);
  };

  const handleCloseForm = () => {
    setIsFormOpen(false);
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

  // Filter options
  const estadoOptions: SelectOption[] = [
    { value: 'TODOS', label: 'Todas las materias' },
    { value: 'true', label: 'Activas' },
    { value: 'false', label: 'Inactivas' },
  ];

  // Table columns
  const columns: TableColumn<MateriaListItem>[] = [
    {
      key: 'codigo',
      header: 'Código',
      render: (materia) => (
        <div>
          <div className="font-medium text-foreground">{materia.codigo}</div>
          <div className="text-sm text-muted-foreground">{materia.nombre}</div>
        </div>
      ),
    },
    {
      key: 'num_coordinadores',
      header: 'Coordinadores',
      render: (materia) => (
        <span className="text-muted-foreground">
          {materia.num_coordinadores}
        </span>
      ),
    },
    {
      key: 'num_comisiones',
      header: 'Comisiones',
      render: (materia) => (
        <span className="text-muted-foreground">
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
        <span className="text-muted-foreground">
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
            <button className="text-muted-foreground hover:text-foreground px-2 py-1">
              •••
            </button>
          }
          items={[
            {
              label: 'Editar',
              onClick: () => handleEdit(materia.id),
              icon: <Pencil className="w-4 h-4" />,
            },
            {
              label: 'Config. dashboard',
              onClick: () => navigate(`/materias/${materia.id}/dashboard`),
              icon: <BarChart3 className="w-4 h-4" />,
            },
            materia.activa
              ? {
                label: 'Eliminar',
                onClick: () => handleDelete(materia.id),
                icon: <Trash2 className="w-4 h-4" />,
                variant: 'danger' as const,
              }
              : {
                label: 'Restaurar',
                onClick: () => handleRestore(materia.id),
                icon: <RotateCcw className="w-4 h-4" />,
              },
          ]}
        />
      ),
    },
  ];

  // Handle filter changes

  const handleEstadoChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      activa: value as 'TODOS' | 'true' | 'false',
      page: 1,
    }));
  };

  // Loading state
  if (isLoading) {
    return <LoadingState title="Cargando materias…" />;
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-destructive mb-4">Error al cargar materias</div>
        <p className="text-muted-foreground mb-4">
          {error instanceof Error ? error.message : 'Error desconocido'}
        </p>
        <Button onClick={() => window.location.reload()}>Reintentar</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground">Materias</h1><HelpButton title="Ayuda — Materias" content={helpContent.materias} /></div>
          <p className="text-sm text-muted-foreground mt-1">
            Gestión de materias y coordinadores
          </p>
        </div>
        <Button onClick={handleCreate}>
          + Crear Materia
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Buscar"
            placeholder="Buscar por código o nombre..."
            value={inputSearch}
            onChange={(e) => setInputSearch(e.target.value)}
          />
          <Select
            label="Estado"
            options={estadoOptions}
            value={filters.activa}
            onChange={(e) => handleEstadoChange(e.target.value)}
          />
        </div>
      </div>

      {/* Results summary */}
      {data?.items && data.items.length > 0 && (
        <div className="text-sm text-muted-foreground">
          Mostrando {data.items.length} de {data.total} materias
        </div>
      )}

      {/* Table */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        {data?.items && data.items.length > 0 ? (
          <Table
            columns={columns}
            data={data.items}
            keyExtractor={(item) => item.id}
          />
        ) : (
          <EmptyState
            icon="📚"
            title="No hay materias"
            description="No se encontraron materias con los filtros aplicados"
            action={
              filters.search || inputSearch || filters.activa !== 'TODOS' ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setInputSearch('');
                    setFilters({
                      activa: 'TODOS',
                      search: '',
                      page: 1,
                      per_page: 20,
                    });
                  }}
                >
                  Limpiar filtros
                </Button>
              ) : (
                <Button onClick={handleCreate}>
                  + Crear primera materia
                </Button>
              )
            }
          />
        )}
      </div>

      {/* Pagination */}
      {data && data.total > data.per_page && (
        <div className="flex justify-center gap-2">
          <Button
            variant="secondary"
            disabled={filters.page === 1}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page - 1 }))
            }
          >
            ← Anterior
          </Button>
          <div className="flex items-center px-4 text-sm text-muted-foreground">
            Página {filters.page} de {Math.ceil(data.total / data.per_page)}
          </div>
          <Button
            variant="secondary"
            disabled={filters.page >= Math.ceil(data.total / data.per_page)}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page + 1 }))
            }
          >
            Siguiente →
          </Button>
        </div>
      )}

      {/* Modal */}
      <MateriaForm
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        materia={editingMateria || undefined}
      />
    </div>
  );
};
