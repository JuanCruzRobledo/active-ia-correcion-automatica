import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, Pencil, Trash2, RotateCcw, MoreVertical } from 'lucide-react';
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
  ResponsiveTable,
  LoadingState,
  HelpButton,
  EmptyState,
  Dropdown,
  ConfirmDialog,
  type TableColumn,
  type SelectOption,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { formatDate } from '@/shared/utils';
import { useTenant } from '@/shared/context/useTenant';

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
  // D2: el rol es de la membresía activa (useTenant), no del usuario global.
  const { rol } = useTenant();
  // El coordinador edita/configura SUS materias pero no crea, borra ni reasigna
  // coordinadores (eso es del admin). El backend lo refuerza (verificar_acceso_materia).
  const isAdmin = rol === 'ADMIN';

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
  // Confirmación de borrado (reemplaza window.confirm)
  const [deletingId, setDeletingId] = useState<number | null>(null);

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

  const handleConfirmDelete = async () => {
    if (deletingId === null) return;
    await deleteMutation.mutateAsync(deletingId);
    setDeletingId(null);
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

  // Menú de acciones (reutilizado en columna desktop y en card mobile)
  const renderActions = (materia: MateriaListItem) => (
    <Dropdown
      trigger={
        <button
          type="button"
          aria-label="Acciones"
          className="inline-flex items-center justify-center min-h-11 min-w-11 -mr-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted touch-manipulation"
        >
          <MoreVertical className="w-5 h-5" />
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
        // Borrar/restaurar es solo del admin.
        ...(isAdmin
          ? [
              materia.activa
                ? {
                    label: 'Eliminar',
                    onClick: () => setDeletingId(materia.id),
                    icon: <Trash2 className="w-4 h-4" />,
                    variant: 'danger' as const,
                  }
                : {
                    label: 'Restaurar',
                    onClick: () => handleRestore(materia.id),
                    icon: <RotateCcw className="w-4 h-4" />,
                  },
            ]
          : []),
      ]}
    />
  );

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
      render: (materia) => renderActions(materia),
    },
  ];

  // Card mobile: codigo/nombre destacados + chips de coordinadores/comisiones +
  // estado + acciones. Mantiene la misma info que la tabla desktop.
  const renderCard = (materia: MateriaListItem) => (
    <div className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium text-foreground break-words">
            {materia.codigo}
          </div>
          <div className="text-sm text-muted-foreground break-words">
            {materia.nombre}
          </div>
        </div>
        <div className="shrink-0">{renderActions(materia)}</div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={materia.activa ? 'success' : 'default'}>
          {materia.activa ? 'Activa' : 'Inactiva'}
        </Badge>
        <span className="text-xs text-muted-foreground">
          {materia.num_coordinadores} coordinadores · {materia.num_comisiones}{' '}
          comisiones
        </span>
      </div>
      <div className="text-xs text-muted-foreground">
        Creada el {formatDate(materia.created_at)}
      </div>
    </div>
  );

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
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><h1 className="text-2xl sm:text-3xl font-bold text-foreground">Materias</h1><HelpButton title="Ayuda — Materias" content={helpContent.materias} /></div>
          <p className="text-sm text-muted-foreground mt-1">
            {isAdmin ? 'Gestión de materias y coordinadores' : 'Tus materias asignadas'}
          </p>
        </div>
        {isAdmin && (
          <Button onClick={handleCreate} className="w-full sm:w-auto">
            + Crear Materia
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Buscar"
            placeholder="Buscar por código o nombre..."
            value={inputSearch}
            onChange={(e) => setInputSearch(e.target.value)}
            inputMode="search"
            enterKeyHint="search"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
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

      {/* Table (desktop) / Cards (mobile) */}
      {data?.items && data.items.length > 0 ? (
        // En desktop la tabla va dentro del card-wrapper; en mobile las cards
        // ya traen su propio borde/bg (lo provee ResponsiveTable).
        <div className="lg:bg-card lg:rounded-lg lg:border lg:border-border lg:overflow-hidden">
          <ResponsiveTable
            columns={columns}
            data={data.items}
            keyExtractor={(item) => item.id}
            renderCard={renderCard}
          />
        </div>
      ) : (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
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
              ) : isAdmin ? (
                <Button onClick={handleCreate}>
                  + Crear primera materia
                </Button>
              ) : undefined
            }
          />
        </div>
      )}

      {/* Pagination */}
      {data && data.total > data.per_page && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="secondary"
            disabled={filters.page === 1}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page - 1 }))
            }
            className="flex-1 sm:flex-none"
          >
            ← Anterior
          </Button>
          <div className="flex shrink-0 items-center px-2 text-center text-sm text-muted-foreground">
            Página {filters.page} de {Math.ceil(data.total / data.per_page)}
          </div>
          <Button
            variant="secondary"
            disabled={filters.page >= Math.ceil(data.total / data.per_page)}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page + 1 }))
            }
            className="flex-1 sm:flex-none"
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
        isAdmin={isAdmin}
      />

      {/* Confirmación de borrado (reemplaza window.confirm) */}
      <ConfirmDialog
        isOpen={deletingId !== null}
        onClose={() => setDeletingId(null)}
        onConfirm={handleConfirmDelete}
        title="Eliminar materia"
        message="¿Estás seguro de que deseas eliminar esta materia?"
        confirmLabel="Eliminar"
        variant="destructive"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
};
