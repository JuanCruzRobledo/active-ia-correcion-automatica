// features/rubricas/pages/RubricasPage.tsx
/**
 * Rubricas management page
 *
 * Displays table of rubricas with filters and CRUD actions
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 6
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { useState } from 'react';
import { FileText, MoreVertical } from 'lucide-react';
import {
  useRubricas,
  useRubrica,
  useDeleteRubrica,
  useRestoreRubrica,
  useDuplicarRubrica,
} from '../hooks';
import type { RubricaListItem, RubricasFilters, TipoRubrica } from '../types';
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
import { RubricaEditor } from '../components';

// Mapeo de tipos a labels legibles
const TIPO_LABELS: Record<TipoRubrica, string> = {
  TP: 'TP',
  PARCIAL_1: 'Parcial 1',
  PARCIAL_2: 'Parcial 2',
  RECUPERATORIO_1: 'Recup. 1',
  RECUPERATORIO_2: 'Recup. 2',
  FINAL: 'Final',
  GLOBAL: 'Global',
};

// Colores para badges de tipo
const TIPO_COLORS: Record<TipoRubrica, 'default' | 'info' | 'warning' | 'success'> = {
  TP: 'info',
  PARCIAL_1: 'warning',
  PARCIAL_2: 'warning',
  RECUPERATORIO_1: 'default',
  RECUPERATORIO_2: 'default',
  FINAL: 'success',
  GLOBAL: 'default',
};

export const RubricasPage = () => {
  const currentYear = new Date().getFullYear();

  const [filters, setFilters] = useState<RubricasFilters>({
    materia_id: undefined,
    tipo: undefined,
    anio: undefined,
    include_inactive: false,
    page: 1,
    per_page: 20,
  });

  const [searchNombre, setSearchNombre] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  // Queries
  const { data, isLoading, error } = useRubricas(filters);
  const { data: materiasData } = useMaterias({ page: 1, per_page: 100 });
  const { data: editingRubrica } = useRubrica(editingId || 0);
  const deleteMutation = useDeleteRubrica();
  const restoreMutation = useRestoreRubrica();
  const duplicarMutation = useDuplicarRubrica();

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

  const handleDelete = async (id: number) => {
    if (window.confirm('¿Estás seguro de que deseas eliminar esta rúbrica?')) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const handleRestore = async (id: number) => {
    await restoreMutation.mutateAsync(id);
  };

  const handleDuplicate = async (id: number) => {
    const nuevoAnio = prompt('¿A qué año deseas duplicar la rúbrica?', String(currentYear + 1));
    if (!nuevoAnio) return;

    const anio = parseInt(nuevoAnio);
    if (isNaN(anio) || anio < 2020 || anio > 2100) {
      alert('Año inválido. Debe estar entre 2020 y 2100.');
      return;
    }

    try {
      await duplicarMutation.mutateAsync({
        id,
        data: { nuevo_anio: anio },
      });
    } catch (error) {
      console.error('Error duplicando rúbrica:', error);
    }
  };

  // Filter options
  const materiaOptions: SelectOption[] = [
    { value: '', label: 'Todas las materias' },
    ...(materiasData?.items || []).map((m) => ({
      value: String(m.id),
      label: `${m.codigo} - ${m.nombre}`,
    })),
  ];

  const tipoOptions: SelectOption[] = [
    { value: '', label: 'Todos los tipos' },
    { value: 'TP', label: 'Trabajo Práctico' },
    { value: 'PARCIAL_1', label: 'Parcial 1' },
    { value: 'PARCIAL_2', label: 'Parcial 2' },
    { value: 'RECUPERATORIO_1', label: 'Recuperatorio 1' },
    { value: 'RECUPERATORIO_2', label: 'Recuperatorio 2' },
    { value: 'FINAL', label: 'Final' },
    { value: 'GLOBAL', label: 'Global' },
  ];

  const estadoOptions: SelectOption[] = [
    { value: 'activas', label: 'Activas' },
    { value: 'todas', label: 'Todas' },
  ];

  // Client-side filter by nombre
  const rubricas = (data?.items || []).filter((rubrica) =>
    searchNombre
      ? rubrica.nombre.toLowerCase().includes(searchNombre.toLowerCase())
      : true
  );

  // Table columns
  const columns: TableColumn<RubricaListItem>[] = [
    {
      key: 'materia',
      header: 'Materia',
      render: (rubrica) => (
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-1/10">
            <FileText className="h-4 w-4 text-accent-1" />
          </div>
          <div>
            <div className="font-medium text-foreground">
              {rubrica.materia_codigo}
            </div>
            <div className="text-xs text-muted-foreground">
              {rubrica.materia_nombre}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'tipo',
      header: 'Tipo',
      render: (rubrica) => (
        <Badge variant={TIPO_COLORS[rubrica.tipo]}>
          {TIPO_LABELS[rubrica.tipo]}
        </Badge>
      ),
    },
    {
      key: 'nombre',
      header: 'Nombre',
      render: (rubrica) => (
        <div>
          <div className="font-medium text-foreground">{rubrica.nombre}</div>
          <div className="text-xs text-muted-foreground">
            #{rubrica.numero} - {rubrica.anio}
          </div>
        </div>
      ),
    },
    {
      key: 'criterios',
      header: 'Criterios',
      render: (rubrica) => (
        <div className="text-sm">
          <div className="text-foreground">{rubrica.num_criterios} criterios</div>
          <div className="text-xs text-muted-foreground">
            {rubrica.puntaje_maximo} pts máx.
          </div>
        </div>
      ),
    },
    {
      key: 'num_entregas',
      header: 'Entregas',
      render: (rubrica) => (
        <span className="text-sm text-foreground">{rubrica.num_entregas}</span>
      ),
    },
    {
      key: 'activa',
      header: 'Estado',
      render: (rubrica) => (
        <Badge variant={rubrica.activa ? 'success' : 'default'}>
          {rubrica.activa ? 'Activa' : 'Inactiva'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Fecha creación',
      render: (rubrica) => (
        <span className="text-sm text-muted-foreground">
          {formatDate(rubrica.created_at)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Acciones',
      className: 'text-right',
      sticky: true,
      render: (rubrica) => (
        <Dropdown
          trigger={
            <Button variant="ghost" size="sm">
              <MoreVertical className="h-4 w-4" />
            </Button>
          }
          items={[
            {
              label: 'Editar',
              onClick: () => handleOpenEdit(rubrica.id),
            },
            {
              label: 'Ver detalle',
              onClick: () => console.log('Ver detalle', rubrica.id),
            },
            {
              label: 'Duplicar a otro año',
              onClick: () => handleDuplicate(rubrica.id),
            },
            {
              label: rubrica.activa ? 'Eliminar' : 'Restaurar',
              onClick: () =>
                rubrica.activa
                  ? handleDelete(rubrica.id)
                  : handleRestore(rubrica.id),
              variant: rubrica.activa ? 'danger' : 'default',
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
      <div className="rounded-lg border border-destructive bg-destructive/10 p-4">
        <p className="text-sm text-destructive">
          Error al cargar rúbricas. Por favor, intenta nuevamente.
        </p>
      </div>
    );
  }

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Rúbricas</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Gestión de criterios de evaluación
          </p>
        </div>
        <Button onClick={handleOpenCreate}>
          + Crear Rúbrica
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <Input
            label="Buscar"
            placeholder="Buscar por nombre..."
            value={searchNombre}
            onChange={(e) => setSearchNombre(e.target.value)}
          />
          <Select
            label="Materia"
            options={materiaOptions}
            value={filters.materia_id?.toString() || ''}
            onChange={(e) => {
              const value = e.target.value;
              setFilters({
                ...filters,
                materia_id: value ? parseInt(value) : undefined,
                page: 1,
              });
            }}
          />
          <Select
            label="Tipo"
            options={tipoOptions}
            value={filters.tipo || ''}
            onChange={(e) => {
              const value = e.target.value as TipoRubrica | '';
              setFilters({
                ...filters,
                tipo: value || undefined,
                page: 1,
              });
            }}
          />
          <Input
            label="Año"
            type="number"
            placeholder={String(currentYear)}
            value={filters.anio?.toString() || ''}
            onChange={(e) => {
              const value = e.target.value;
              setFilters({
                ...filters,
                anio: value ? parseInt(value) : undefined,
                page: 1,
              });
            }}
          />
          <Select
            label="Estado"
            options={estadoOptions}
            value={filters.include_inactive ? 'todas' : 'activas'}
            onChange={(e) => {
              setFilters({
                ...filters,
                include_inactive: e.target.value === 'todas',
                page: 1,
              });
            }}
          />
        </div>
      </div>

      {/* Results summary */}
      {rubricas.length > 0 && (
        <div className="text-sm text-muted-foreground">
          Mostrando {rubricas.length} de {data?.total || 0} rúbricas
        </div>
      )}

      {/* Table */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        {rubricas.length > 0 ? (
          <Table
            columns={columns}
            data={rubricas}
            keyExtractor={(rubrica) => rubrica.id}
          />
        ) : (
          <EmptyState
            icon={<FileText className="h-12 w-12 text-muted-foreground" />}
            title="No hay rúbricas"
            description={
              searchNombre || filters.materia_id || filters.tipo || filters.anio
                ? 'No se encontraron rúbricas con los filtros aplicados'
                : 'No se encontraron rúbricas. Crea la primera para empezar.'
            }
            action={
              <Button onClick={handleOpenCreate}>
                + Crear primera rúbrica
              </Button>
            }
          />
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="secondary"
            disabled={filters.page === 1}
            onClick={() =>
              setFilters((f) => ({ ...f, page: Math.max(1, f.page! - 1) }))
            }
          >
            ← Anterior
          </Button>
          <div className="flex items-center px-4 text-sm text-muted-foreground">
            Página {filters.page} de {totalPages}
          </div>
          <Button
            variant="secondary"
            disabled={filters.page === totalPages}
            onClick={() =>
              setFilters((f) => ({
                ...f,
                page: Math.min(totalPages, f.page! + 1),
              }))
            }
          >
            Siguiente →
          </Button>
        </div>
      )}

      {/* Create/Edit Modal */}
      <RubricaEditor
        isOpen={showForm}
        onClose={handleCloseForm}
        materiaId={filters.materia_id}
        rubrica={editingRubrica}
      />
    </div>
  );
};
