// features/comisiones/pages/ComisionesPage.tsx
/**
 * Comisiones management page for Admin role
 *
 * Displays table of comisiones with filters and CRUD actions
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 5
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { useState } from 'react';
import { FolderOpen, Pencil, Trash2, RotateCcw } from 'lucide-react';
import {
  useComisiones,
  useComision,
  useDeleteComision,
  useRestoreComision,
} from '../hooks';
import type { ComisionListItem, ComisionesFilters } from '../types';
import { ComisionForm } from '../components';
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
  type DropdownItem,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { formatDate } from '@/shared/utils';
import { useMaterias } from '@/features/materias/hooks';
import { useAuth } from '@/features/auth/hooks';

export const ComisionesPage = () => {
  const [filters, setFilters] = useState<ComisionesFilters>({
    materia_id: undefined,
    anio: undefined,
    include_inactive: false,
    page: 1,
    per_page: 20,
  });

  const [searchNombre, setSearchNombre] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  // Queries
  const { data, isLoading, error } = useComisiones(filters);
  const { user } = useAuth();
  const isTutor = user?.rol === 'TUTOR';
  // Wait for user to load before deciding if we can call admin-only endpoints
  const canListMaterias = !!user && !isTutor;
  const { data: materiasData, isLoading: materiasLoading } = useMaterias(
    { page: 1, per_page: 100 },
    { enabled: canListMaterias }
  );
  const { data: editingComision } = useComision(editingId || 0);
  const deleteMutation = useDeleteComision();
  const restoreMutation = useRestoreComision();
  const sinMateriasAsignadas =
    user?.rol === 'COORDINADOR' &&
    !materiasLoading &&
    (materiasData?.items?.length ?? 0) === 0;

  // Form handlers
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

  // Filter options — for tutors, derive materias from their assigned comisiones
  // (they don't have permission to list /materias)
  const materiaOptionsSource = isTutor
    ? Array.from(
        new Map(
          (data?.items ?? []).map((c) => [
            c.materia_id,
            {
              id: c.materia_id,
              codigo: c.materia_codigo,
              nombre: c.materia_nombre,
            },
          ])
        ).values()
      )
    : (materiasData?.items ?? []);

  const materiaOptions: SelectOption[] = [
    { value: '', label: 'Todas las materias' },
    ...materiaOptionsSource.map((materia) => ({
      value: String(materia.id),
      label: `${materia.codigo} - ${materia.nombre}`,
    })),
  ];

  const estadoOptions: SelectOption[] = [
    { value: 'false', label: 'Solo activas' },
    { value: 'true', label: 'Incluir eliminadas' },
  ];

  // Handle filter changes
  const handleMateriaChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      materia_id: value ? Number(value) : undefined,
      page: 1,
    }));
  };

  const handleAnioChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      anio: value ? Number(value) : undefined,
      page: 1,
    }));
  };

  const handleEstadoChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      include_inactive: value === 'true',
      page: 1,
    }));
  };

  const handleSearchChange = (value: string) => {
    setSearchNombre(value);
  };

  // Filter data by nombre search (client-side)
  const filteredData = data?.items.filter((comision) =>
    searchNombre
      ? comision.nombre.toLowerCase().includes(searchNombre.toLowerCase()) ||
        comision.materia_nombre.toLowerCase().includes(searchNombre.toLowerCase())
      : true
  );

  // Table columns
  const columns: TableColumn<ComisionListItem>[] = [
    {
      key: 'materia',
      header: 'Materia',
      render: (comision) => (
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
            <FolderOpen className="h-4 w-4 text-accent" />
          </div>
          <div>
            <div className="font-medium text-foreground">
              {comision.materia_codigo}
            </div>
            <div className="text-sm text-muted-foreground">{comision.materia_nombre}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'nombre',
      header: 'Comisión',
      render: (comision) => (
        <div>
          <div className="font-medium text-foreground">{comision.nombre}</div>
          <div className="text-sm text-muted-foreground">Año {comision.anio}</div>
        </div>
      ),
    },
    {
      key: 'num_tutores',
      header: 'Tutores',
      render: (comision) => (
        <span className="text-sm text-foreground">
          {comision.num_tutores} {comision.num_tutores === 1 ? 'tutor' : 'tutores'}
        </span>
      ),
    },
    {
      key: 'num_entregas',
      header: 'Entregas',
      render: (comision) => (
        <span className="text-sm text-foreground">{comision.num_entregas}</span>
      ),
    },
    {
      key: 'activa',
      header: 'Estado',
      render: (comision) => (
        <Badge variant={comision.activa ? 'success' : 'default'}>
          {comision.activa ? 'Activa' : 'Eliminada'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Fecha creación',
      render: (comision) => (
        <span className="text-sm text-muted-foreground">
          {formatDate(comision.created_at)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Acciones',
      className: 'text-right',
      sticky: true,
      render: (comision) => {
        const items: DropdownItem[] = [
          {
            label: isTutor ? 'Editar Moodle' : 'Editar',
            onClick: () => handleOpenEdit(comision.id),
            icon: <Pencil className="w-4 h-4" />,
          },
        ];
        if (!isTutor) {
          items.push(
            comision.activa
              ? {
                  label: 'Eliminar',
                  onClick: () => {
                    if (
                      window.confirm(
                        `¿Estás seguro de eliminar la comisión "${comision.nombre}"?`
                      )
                    ) {
                      deleteMutation.mutate(comision.id);
                    }
                  },
                  icon: <Trash2 className="w-4 h-4" />,
                  variant: 'danger' as const,
                }
              : {
                  label: 'Restaurar',
                  onClick: () => restoreMutation.mutate(comision.id),
                  icon: <RotateCcw className="w-4 h-4" />,
                }
          );
        }
        return (
          <Dropdown
            trigger={
              <button className="text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted">
                •••
              </button>
            }
            items={items}
          />
        );
      },
    },
  ];

  // Loading state
  if (isLoading) {
    return <LoadingState title="Cargando comisiones…" />;
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-destructive mb-4">Error al cargar comisiones</div>
        <p className="text-muted-foreground mb-4">
          {error instanceof Error ? error.message : 'Error desconocido'}
        </p>
        <Button onClick={() => window.location.reload()}>Reintentar</Button>
      </div>
    );
  }

  const hasActiveFilters =
    filters.materia_id ||
    filters.anio ||
    searchNombre ||
    filters.include_inactive;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground">Comisiones</h1><HelpButton title="Ayuda — Comisiones" content={helpContent.comisiones} /></div>
          <p className="text-sm text-muted-foreground mt-1">
            {isTutor
              ? 'Editá la configuración de Moodle de tus comisiones asignadas'
              : 'Gestiona las comisiones de cada materia'}
          </p>
        </div>
        {!sinMateriasAsignadas && !isTutor && (
          <Button onClick={handleOpenCreate}>
            + Crear Comisión
          </Button>
        )}
      </div>

      {/* Filters */}
      {!sinMateriasAsignadas && (
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Input
            label="Buscar"
            placeholder="Buscar por nombre..."
            value={searchNombre}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
          <Select
            label="Materia"
            options={materiaOptions}
            value={filters.materia_id ? String(filters.materia_id) : ''}
            onChange={(e) => handleMateriaChange(e.target.value)}
          />
          <Input
            label="Año"
            type="number"
            placeholder="Ej: 2026"
            value={filters.anio || ''}
            onChange={(e) => handleAnioChange(e.target.value)}
            min="2020"
            max="2100"
          />
          {!isTutor && (
            <Select
              label="Estado"
              options={estadoOptions}
              value={String(filters.include_inactive)}
              onChange={(e) => handleEstadoChange(e.target.value)}
            />
          )}
        </div>
      </div>
      )}

      {/* Results summary */}
      {filteredData && filteredData.length > 0 && (
        <div className="text-sm text-muted-foreground">
          Mostrando {filteredData.length} de {data?.total} comisiones
        </div>
      )}

      {/* Table */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        {filteredData && filteredData.length > 0 ? (
          <Table
            columns={columns}
            data={filteredData}
            keyExtractor={(item) => item.id}
          />
        ) : (
          <EmptyState
            icon="📚"
            title={sinMateriasAsignadas ? 'Sin materias asignadas' : 'No hay comisiones'}
            description={
              sinMateriasAsignadas
                ? 'No tienes materias asignadas actualmente. Un administrador debe asignarte materias para que puedas gestionar comisiones.'
                : hasActiveFilters
                  ? 'No se encontraron comisiones con los filtros aplicados'
                  : 'No hay comisiones creadas aún'
            }
            action={
              sinMateriasAsignadas ? undefined : hasActiveFilters ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setFilters({
                      materia_id: undefined,
                      anio: undefined,
                      include_inactive: false,
                      page: 1,
                      per_page: 20,
                    });
                    setSearchNombre('');
                  }}
                >
                  Limpiar filtros
                </Button>
              ) : isTutor ? undefined : (
                <Button onClick={handleOpenCreate}>
                  + Crear primera comisión
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
              setFilters((prev) => ({ ...prev, page: prev.page! - 1 }))
            }
          >
            ← Anterior
          </Button>
          <div className="flex items-center px-4 text-sm text-muted-foreground">
            Página {filters.page} de {Math.ceil(data.total / data.per_page)}
          </div>
          <Button
            variant="secondary"
            disabled={filters.page! >= Math.ceil(data.total / data.per_page)}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page! + 1 }))
            }
          >
            Siguiente →
          </Button>
        </div>
      )}

      {/* Form Modal */}
      <ComisionForm
        isOpen={showForm}
        onClose={handleCloseForm}
        comision={editingId ? editingComision : undefined}
      />
    </div>
  );
};
