// features/rubricas/pages/RubricasPage.tsx
/**
 * Rubricas management page
 *
 * Displays table of rubricas with filters and CRUD actions
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 6
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { useState } from 'react';
import toast from 'react-hot-toast';
import { FileText, MoreVertical, Pencil, Copy, Trash2, RotateCcw, Download, FileDown, FileJson, AlertTriangle } from 'lucide-react';
import {
  useRubricas,
  useRubrica,
  useDeleteRubrica,
  useRestoreRubrica,
  useDuplicarRubrica,
  useDownloadRubricaPDF,
  useDownloadRubricaPDFResumido,
} from '../hooks';
import type { RubricaListItem, RubricasFilters, TipoRubrica } from '../types';
import {
  Button,
  Input,
  Select,
  Badge,
  ResponsiveTable,
  LoadingState,
  HelpButton,
  RefreshButton,
  NovedadesBanner,
  EmptyState,
  Dropdown,
  ConfirmDialog,
  Modal,
  type TableColumn,
  type SelectOption,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { formatDate } from '@/shared/utils';
import { useMaterias } from '@/features/materias/hooks';
import { useAuth } from '@/features/auth/hooks';
import { useNovedades } from '@/shared/hooks/useNovedades';
import { mensajeNovedades } from '@/shared/utils/novedades';
import { RubricaEditor } from '../components';
import { rubricasService } from '../services/rubricas-service';

// Mapeo de tipos a labels legibles
const TIPO_LABELS: Record<TipoRubrica, string> = {
  TP: 'TP',
  TPI: 'TPI',
  PARCIAL_1: 'Parcial 1',
  PARCIAL_2: 'Parcial 2',
  RECUPERATORIO_1: 'Recup. 1',
  RECUPERATORIO_2: 'Recup. 2',
  FINAL: 'Final',
  GLOBAL: 'Global',
};

// Mapeo de tipos a labels completos para usar en nombres de archivo
const TIPO_LABELS_FILENAME: Record<TipoRubrica, string> = {
  TP: 'TP',
  TPI: 'Trabajo Práctico Integrador',
  PARCIAL_1: 'Parcial 1',
  PARCIAL_2: 'Parcial 2',
  RECUPERATORIO_1: 'Recuperatorio 1',
  RECUPERATORIO_2: 'Recuperatorio 2',
  FINAL: 'Final',
  GLOBAL: 'Global',
};

// Colores para badges de tipo
const TIPO_COLORS: Record<TipoRubrica, 'default' | 'info' | 'warning' | 'success'> = {
  TP: 'info',
  TPI: 'info',
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

  // Confirmación de borrado (reemplaza window.confirm)
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);

  // Duplicado a otro año (reemplaza window.prompt)
  const [duplicateTargetId, setDuplicateTargetId] = useState<number | null>(null);
  const [duplicateAnio, setDuplicateAnio] = useState('');
  const [duplicateError, setDuplicateError] = useState<string | null>(null);

  // Queries
  const { data, isLoading, error, refetch, isFetching } = useRubricas(filters);
  const { hayNovedades, aceptar: aceptarNovedades } = useNovedades('rubricas');
  const { data: materiasData, isLoading: materiasLoading } = useMaterias({ page: 1, per_page: 100 });
  const { data: editingRubrica } = useRubrica(editingId || 0);
  const deleteMutation = useDeleteRubrica();
  const restoreMutation = useRestoreRubrica();
  const duplicarMutation = useDuplicarRubrica();
  const downloadPDFMutation = useDownloadRubricaPDF();
  const downloadPDFResumidoMutation = useDownloadRubricaPDFResumido();

  const { user } = useAuth();
  const sinMateriasAsignadas =
    user?.rol === 'COORDINADOR' &&
    !materiasLoading &&
    (materiasData?.items?.length ?? 0) === 0;

  // Descargar el JSON portable requiere el detalle (GET /rubricas/{id}), endpoint
  // coordinador/admin-only. Un TUTOR recibiría 403, así que gateamos el ítem en el
  // front (mejor UX que un toast de error) — mismo criterio de rol que ya usa la página.
  const puedeDescargarJSON = user?.rol === 'COORDINADOR' || user?.rol === 'ADMIN';

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

  const handleConfirmDelete = async () => {
    if (deleteTargetId === null) return;
    await deleteMutation.mutateAsync(deleteTargetId);
    setDeleteTargetId(null);
  };

  const handleRestore = async (id: number) => {
    await restoreMutation.mutateAsync(id);
  };

  const handleOpenDuplicate = (id: number) => {
    setDuplicateTargetId(id);
    setDuplicateAnio(String(currentYear + 1));
    setDuplicateError(null);
  };

  const handleConfirmDuplicate = async () => {
    if (duplicateTargetId === null) return;

    const anio = parseInt(duplicateAnio);
    if (isNaN(anio) || anio < 2020 || anio > 2100) {
      setDuplicateError('Año inválido. Debe estar entre 2020 y 2100.');
      return;
    }

    try {
      await duplicarMutation.mutateAsync({
        id: duplicateTargetId,
        data: { nuevo_anio: anio },
      });
      setDuplicateTargetId(null);
    } catch (error) {
      console.error('Error duplicando rúbrica:', error);
      setDuplicateError('No se pudo duplicar la rúbrica. Intenta nuevamente.');
    }
  };

  const handleDownloadPDF = async (rubrica: RubricaListItem) => {
    try {
      const tipoLabel = TIPO_LABELS_FILENAME[rubrica.tipo];
      const filename = `${tipoLabel} ${rubrica.numero} - ${rubrica.titulo}.pdf`;
      await downloadPDFMutation.mutateAsync({ id: rubrica.id, filename });
    } catch (error) {
      console.error('Error descargando PDF:', error);
      toast.error('Error al descargar el PDF. Por favor, intenta nuevamente.');
    }
  };

  const handleDownloadPDFResumido = async (rubrica: RubricaListItem) => {
    try {
      const tipoLabel = TIPO_LABELS_FILENAME[rubrica.tipo];
      const filename = `${tipoLabel} ${rubrica.numero} - ${rubrica.titulo} (Guia Estudiantes).pdf`;
      await downloadPDFResumidoMutation.mutateAsync({ id: rubrica.id, filename });
    } catch (error) {
      console.error('Error descargando guía para estudiantes:', error);
      toast.error('Error al descargar la guía para estudiantes. Por favor, intenta nuevamente.');
    }
  };

  const handleDownloadJSON = async (rubrica: RubricaListItem) => {
    try {
      const tipoLabel = TIPO_LABELS_FILENAME[rubrica.tipo];
      const filename = `${tipoLabel} ${rubrica.numero} - ${rubrica.titulo}.json`;
      await rubricasService.downloadJSON(rubrica.id, filename);
    } catch (error) {
      console.error('Error descargando JSON:', error);
      toast.error('Error al descargar el JSON. Por favor, intenta nuevamente.');
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

  // Client-side filter by titulo
  const rubricas = (data?.items || []).filter((rubrica) =>
    searchNombre
      ? rubrica.titulo.toLowerCase().includes(searchNombre.toLowerCase())
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
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground">{rubrica.titulo}</span>
            {rubrica.schema_version < 2 && (
              <Badge variant="warning" title="Rúbrica desactualizada — actualizar al nuevo modelo">
                <AlertTriangle className="h-3 w-3 mr-1 inline" />
                Desactualizada
              </Badge>
            )}
          </div>
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
              icon: <Pencil className="w-4 h-4" />,
            },
            {
              label: 'Duplicar a otro año',
              onClick: () => handleOpenDuplicate(rubrica.id),
              icon: <Copy className="w-4 h-4" />,
            },
            {
              label: 'Descargar PDF Completo',
              onClick: () => handleDownloadPDF(rubrica),
              icon: <Download className="w-4 h-4" />,
            },
            {
              label: 'Descargar Guía para Estudiantes',
              onClick: () => handleDownloadPDFResumido(rubrica),
              icon: <FileDown className="w-4 h-4" />,
            },
            ...(puedeDescargarJSON
              ? [
                  {
                    label: 'Descargar JSON',
                    onClick: () => handleDownloadJSON(rubrica),
                    icon: <FileJson className="w-4 h-4" />,
                  },
                ]
              : []),
            rubrica.activa
              ? {
                label: 'Eliminar',
                onClick: () => setDeleteTargetId(rubrica.id),
                icon: <Trash2 className="w-4 h-4" />,
                variant: 'danger' as const,
              }
              : {
                label: 'Restaurar',
                onClick: () => handleRestore(rubrica.id),
                icon: <RotateCcw className="w-4 h-4" />,
              },
          ]}
        />
      ),
    },
  ];

  if (isLoading) {
    return <LoadingState title="Cargando rúbricas…" />;
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
    <div className="space-y-4 sm:space-y-6">
      {/* Banner "hay novedades" (item #2, Capa B): otra sesión cambió las rúbricas. */}
      {hayNovedades && (
        <NovedadesBanner
          mensaje={mensajeNovedades(user?.rol)}
          onActualizar={() => {
            refetch();
            aceptarNovedades();
          }}
        />
      )}
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground sm:text-3xl">Rúbricas</h1><HelpButton title="Ayuda — Rúbricas" content={helpContent.rubricas} /></div>
          <p className="text-sm text-muted-foreground mt-1">
            Gestión de criterios de evaluación
          </p>
        </div>
        <div className="flex items-center gap-2">
          <RefreshButton onRefresh={() => refetch()} isRefreshing={isFetching} />
          {!sinMateriasAsignadas && (
            <Button onClick={handleOpenCreate} className="w-full sm:w-auto">
              + Crear Rúbrica
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      {!sinMateriasAsignadas && (
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
              inputMode="numeric"
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
      )}

      {/* Results summary */}
      {rubricas.length > 0 && (
        <div className="text-sm text-muted-foreground">
          Mostrando {rubricas.length} de {data?.total || 0} rúbricas
        </div>
      )}

      {/* Table (desktop) / Cards (mobile) */}
      {rubricas.length > 0 ? (
        <div className="bg-card rounded-lg border border-border overflow-hidden lg:p-0">
          <ResponsiveTable
            columns={columns}
            data={rubricas}
            keyExtractor={(rubrica) => rubrica.id}
            cardClassName="p-3 sm:p-4"
            renderCard={(rubrica) => (
              <div className="flex flex-col gap-3">
                {/* Materia + acciones */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-1/10">
                      <FileText className="h-4 w-4 text-accent-1" />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate font-medium text-foreground">
                        {rubrica.materia_codigo}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        {rubrica.materia_nombre}
                      </div>
                    </div>
                  </div>
                  <div className="shrink-0">
                    {columns.find((c) => c.key === 'actions')?.render?.(rubrica)}
                  </div>
                </div>

                {/* Título */}
                <div>
                  <div className="font-medium text-foreground break-words">{rubrica.titulo}</div>
                  <div className="text-xs text-muted-foreground">
                    #{rubrica.numero} - {rubrica.anio}
                  </div>
                </div>

                {/* Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={TIPO_COLORS[rubrica.tipo]}>{TIPO_LABELS[rubrica.tipo]}</Badge>
                  <Badge variant={rubrica.activa ? 'success' : 'default'}>
                    {rubrica.activa ? 'Activa' : 'Inactiva'}
                  </Badge>
                  {rubrica.schema_version < 2 && (
                    <Badge variant="warning">
                      <AlertTriangle className="h-3 w-3 mr-1 inline" />
                      Desactualizada
                    </Badge>
                  )}
                </div>

                {/* Stats */}
                <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  <div className="flex items-center gap-1.5">
                    <dt className="text-muted-foreground">Criterios:</dt>
                    <dd className="text-foreground">
                      {rubrica.num_criterios} ({rubrica.puntaje_maximo} pts máx.)
                    </dd>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <dt className="text-muted-foreground">Entregas:</dt>
                    <dd className="text-foreground">{rubrica.num_entregas}</dd>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <dt className="text-muted-foreground">Creada:</dt>
                    <dd className="text-foreground">{formatDate(rubrica.created_at)}</dd>
                  </div>
                </dl>
              </div>
            )}
          />
        </div>
      ) : (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <EmptyState
            icon={<FileText className="h-12 w-12 text-muted-foreground" />}
            title={sinMateriasAsignadas ? 'Sin materias asignadas' : 'No hay rúbricas'}
            description={
              sinMateriasAsignadas
                ? 'No tienes materias asignadas actualmente. Un administrador debe asignarte materias para que puedas gestionar rúbricas.'
                : searchNombre || filters.materia_id || filters.tipo || filters.anio
                  ? 'No se encontraron rúbricas con los filtros aplicados'
                  : 'No se encontraron rúbricas. Crea la primera para empezar.'
            }
            action={
              sinMateriasAsignadas ? undefined : (
                <Button onClick={handleOpenCreate} className="w-full sm:w-auto">
                  + Crear primera rúbrica
                </Button>
              )
            }
          />
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="secondary"
            disabled={filters.page === 1}
            className="flex-1 sm:flex-none"
            onClick={() =>
              setFilters((f) => ({ ...f, page: Math.max(1, f.page! - 1) }))
            }
          >
            ← Anterior
          </Button>
          <div className="flex items-center px-2 text-center text-sm text-muted-foreground sm:px-4">
            Página {filters.page} de {totalPages}
          </div>
          <Button
            variant="secondary"
            disabled={filters.page === totalPages}
            className="flex-1 sm:flex-none"
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
        rubrica={editingRubrica}
      />

      {/* Confirmación de borrado */}
      <ConfirmDialog
        isOpen={deleteTargetId !== null}
        onClose={() => setDeleteTargetId(null)}
        onConfirm={handleConfirmDelete}
        title="Eliminar rúbrica"
        message="¿Estás seguro de que deseas eliminar esta rúbrica? Esta acción la marcará como inactiva."
        confirmLabel="Eliminar"
        variant="destructive"
        isLoading={deleteMutation.isPending}
      />

      {/* Duplicar a otro año */}
      <Modal
        isOpen={duplicateTargetId !== null}
        onClose={() => setDuplicateTargetId(null)}
        title="Duplicar rúbrica"
        size="md"
        footer={
          <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              variant="outline"
              onClick={() => setDuplicateTargetId(null)}
              disabled={duplicarMutation.isPending}
              className="w-full sm:w-auto"
            >
              Cancelar
            </Button>
            <Button
              onClick={handleConfirmDuplicate}
              isLoading={duplicarMutation.isPending}
              className="w-full sm:w-auto"
            >
              Duplicar
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Se creará una copia de la rúbrica para el año indicado.
          </p>
          <Input
            label="Año destino"
            type="number"
            inputMode="numeric"
            min={2020}
            max={2100}
            value={duplicateAnio}
            onChange={(e) => {
              setDuplicateAnio(e.target.value);
              setDuplicateError(null);
            }}
            error={duplicateError ?? undefined}
            placeholder={String(currentYear + 1)}
          />
        </div>
      </Modal>
    </div>
  );
};
