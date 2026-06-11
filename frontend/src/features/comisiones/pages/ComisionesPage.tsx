// features/comisiones/pages/ComisionesPage.tsx
/**
 * Comisiones management page for Admin role
 *
 * Displays table of comisiones with filters and CRUD actions
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 5
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { useState } from 'react';
import { FolderOpen, Pencil, Trash2, RotateCcw, MoreVertical } from 'lucide-react';
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
  ResponsiveTable,
  ConfirmDialog,
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
  const [deleteTarget, setDeleteTarget] = useState<ComisionListItem | null>(null);

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

  // Acciones de fila (reutilizadas por la tabla desktop y la card mobile).
  const buildActionItems = (comision: ComisionListItem): DropdownItem[] => {
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
              onClick: () => setDeleteTarget(comision),
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
    return items;
  };

  // Trigger tactil (>=44px en mobile) del menu de acciones.
  const renderActionsTrigger = (comision: ComisionListItem) => (
    <Dropdown
      trigger={
        <button
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground touch-manipulation sm:min-h-9 sm:min-w-9"
          aria-label="Acciones"
        >
          <MoreVertical className="h-5 w-5" />
        </button>
      }
      items={buildActionItems(comision)}
    />
  );

  // Card mobile: misma informacion que la fila, apilada y tactil.
  const renderComisionCard = (comision: ComisionListItem) => (
    <div className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10">
            <FolderOpen className="h-5 w-5 text-accent" />
          </div>
          <div className="min-w-0">
            <div className="font-medium text-foreground truncate">
              {comision.nombre}
            </div>
            <div className="text-sm text-muted-foreground truncate">
              {comision.materia_codigo} · {comision.materia_nombre}
            </div>
          </div>
        </div>
        <div className="shrink-0">{renderActionsTrigger(comision)}</div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Badge variant={comision.activa ? 'success' : 'default'}>
          {comision.activa ? 'Activa' : 'Eliminada'}
        </Badge>
        <span>Año {comision.anio}</span>
        <span aria-hidden="true">·</span>
        <span>
          {comision.num_tutores}{' '}
          {comision.num_tutores === 1 ? 'tutor' : 'tutores'}
        </span>
        <span aria-hidden="true">·</span>
        <span>{comision.num_entregas} entregas</span>
      </div>

      <div className="text-xs text-muted-foreground">
        Creada el {formatDate(comision.created_at)}
      </div>
    </div>
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
      render: (comision) => renderActionsTrigger(comision),
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
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground sm:text-3xl">Comisiones</h1><HelpButton title="Ayuda — Comisiones" content={helpContent.comisiones} /></div>
          <p className="text-sm text-muted-foreground mt-1">
            {isTutor
              ? 'Editá la configuración de Moodle de tus comisiones asignadas'
              : 'Gestiona las comisiones de cada materia'}
          </p>
        </div>
        {!sinMateriasAsignadas && !isTutor && (
          <Button onClick={handleOpenCreate} className="w-full sm:w-auto">
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
            type="search"
            inputMode="search"
            enterKeyHint="search"
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
            inputMode="numeric"
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

      {/* Table (desktop) / Cards (mobile) */}
      {filteredData && filteredData.length > 0 ? (
        // El borde/fondo tipo "card" solo aplica en desktop (lg:), donde se
        // renderiza la <table>. En mobile, cada tarjeta de ResponsiveTable ya
        // trae su propio borde/fondo, asi que el wrapper queda transparente.
        <div className="lg:bg-card lg:rounded-lg lg:border lg:border-border lg:overflow-hidden">
          <ResponsiveTable
            columns={columns}
            data={filteredData}
            keyExtractor={(item) => item.id}
            renderCard={renderComisionCard}
          />
        </div>
      ) : (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
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
                  className="w-full sm:w-auto"
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
                <Button onClick={handleOpenCreate} className="w-full sm:w-auto">
                  + Crear primera comisión
                </Button>
              )
            }
          />
        </div>
      )}

      {/* Pagination */}
      {data && data.total > data.per_page && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="secondary"
            className="flex-1 min-h-11 sm:flex-none"
            disabled={filters.page === 1}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page! - 1 }))
            }
          >
            ← Anterior
          </Button>
          <div className="flex items-center px-2 text-center text-sm text-muted-foreground sm:px-4">
            Página {filters.page} de {Math.ceil(data.total / data.per_page)}
          </div>
          <Button
            variant="secondary"
            className="flex-1 min-h-11 sm:flex-none"
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

      {/* Confirmación de eliminación (reemplaza window.confirm) */}
      <ConfirmDialog
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget.id, {
              onSuccess: () => setDeleteTarget(null),
            });
          }
        }}
        title="Eliminar comisión"
        message={
          deleteTarget
            ? `¿Estás seguro de eliminar la comisión "${deleteTarget.nombre}"?`
            : ''
        }
        confirmLabel="Eliminar"
        variant="destructive"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
};
