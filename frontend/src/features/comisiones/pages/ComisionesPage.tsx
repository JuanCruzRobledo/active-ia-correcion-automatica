// features/comisiones/pages/ComisionesPage.tsx
/**
 * Comisiones management page for Admin role
 *
 * Displays table of comisiones with filters and CRUD actions
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 5
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { useState } from 'react';
import { FolderOpen } from 'lucide-react';
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
  Spinner,
  EmptyState,
  Dropdown,
  type TableColumn,
  type SelectOption,
} from '@/shared/components/ui';
import { formatDate } from '@/shared/utils';
import { useMaterias } from '@/features/materias/hooks';

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
  const { data: materiasData } = useMaterias({ page: 1, per_page: 100 });
  const { data: editingComision } = useComision(editingId || 0);
  const deleteMutation = useDeleteComision();
  const restoreMutation = useRestoreComision();

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

  // Filter options
  const materiaOptions: SelectOption[] = [
    { value: '', label: 'Todas las materias' },
    ...(materiasData?.items || []).map((materia) => ({
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
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
            <FolderOpen className="h-4 w-4 text-blue-600" />
          </div>
          <div>
            <div className="font-medium text-gray-900">
              {comision.materia_codigo}
            </div>
            <div className="text-sm text-gray-500">{comision.materia_nombre}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'nombre',
      header: 'Comisión',
      render: (comision) => (
        <div>
          <div className="font-medium text-gray-900">{comision.nombre}</div>
          <div className="text-sm text-gray-500">Año {comision.anio}</div>
        </div>
      ),
    },
    {
      key: 'num_tutores',
      header: 'Tutores',
      render: (comision) => (
        <span className="text-sm text-gray-700">
          {comision.num_tutores} {comision.num_tutores === 1 ? 'tutor' : 'tutores'}
        </span>
      ),
    },
    {
      key: 'num_entregas',
      header: 'Entregas',
      render: (comision) => (
        <span className="text-sm text-gray-700">{comision.num_entregas}</span>
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
        <span className="text-sm text-gray-500">
          {formatDate(comision.created_at)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Acciones',
      className: 'text-right',
      sticky: true,
      render: (comision) => (
        <Dropdown
          trigger={
            <button className="text-gray-400 hover:text-gray-600 px-2 py-1 rounded hover:bg-gray-100">
              •••
            </button>
          }
          items={[
            {
              label: 'Editar',
              onClick: () => handleOpenEdit(comision.id),
              icon: '✏️',
            },
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
                  icon: '🗑️',
                  variant: 'danger' as const,
                }
              : {
                  label: 'Restaurar',
                  onClick: () => restoreMutation.mutate(comision.id),
                  icon: '↩️',
                },
          ]}
        />
      ),
    },
  ];

  // Loading state
  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 mb-4">Error al cargar comisiones</div>
        <p className="text-gray-500 mb-4">
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
          <h1 className="text-2xl font-bold text-gray-900">Comisiones</h1>
          <p className="text-sm text-gray-500 mt-1">
            Gestiona las comisiones de cada materia
          </p>
        </div>
        <Button onClick={handleOpenCreate}>
          + Crear Comisión
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
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
          <Select
            label="Estado"
            options={estadoOptions}
            value={String(filters.include_inactive)}
            onChange={(e) => handleEstadoChange(e.target.value)}
          />
        </div>
      </div>

      {/* Results summary */}
      {filteredData && filteredData.length > 0 && (
        <div className="text-sm text-gray-500">
          Mostrando {filteredData.length} de {data?.total} comisiones
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {filteredData && filteredData.length > 0 ? (
          <Table
            columns={columns}
            data={filteredData}
            keyExtractor={(item) => item.id}
          />
        ) : (
          <EmptyState
            icon="📚"
            title="No hay comisiones"
            description={
              hasActiveFilters
                ? 'No se encontraron comisiones con los filtros aplicados'
                : 'No hay comisiones creadas aún'
            }
            action={
              hasActiveFilters ? (
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
              ) : (
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
          <div className="flex items-center px-4 text-sm text-gray-600">
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
