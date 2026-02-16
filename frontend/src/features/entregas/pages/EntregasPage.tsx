// features/entregas/pages/EntregasPage.tsx
/**
 * EntregasPage - Main page for managing student submissions.
 *
 * Displays a table of entregas with filters, search, and actions.
 * Tutors can view, upload, manage, and correct student submissions.
 *
 * Consolidated with correction features (formerly CorreccionesPage)
 * Ref: docs/specs/07-DISENO-UI-UX.md section 4.2
 */

import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useEntregas, useDeleteEntrega, useCorregirEntregaMasiva, useCorregirEntrega } from '../hooks';
import { useComisiones } from '@/features/comisiones/hooks';
import { useRubricas } from '@/features/rubricas/hooks';
import { useCorreccionByEntrega, useRecorregirEntrega } from '@/features/correcciones/hooks/useCorrecciones';
import {
  descargarPDFCorreccion,
  descargarTodosPDFs,
  // exportarExcel, // Temporalmente deshabilitado
} from '@/features/correcciones/services/correcciones-service';
import { CargaEntregaModal, EntregaViewModal } from '../components';
import CorreccionViewEditModal from '@/features/correcciones/components/CorreccionViewEditModal';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Select } from '@/shared/components/ui/Select';
import { Checkbox } from '@/shared/components/ui/Checkbox';
import { Badge } from '@/shared/components/ui/Badge';
import { Spinner } from '@/shared/components/ui/Spinner';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { Dropdown } from '@/shared/components/ui/Dropdown';
import {
  FileUp,
  Search,
  MoreVertical,
  Eye,
  Trash2,
  FileCheck2,
  Upload,
  Download,
  RefreshCw,
  FileText,
} from 'lucide-react';
import type { EstadoEntrega, EntregaListItem } from '../types';

const ESTADO_OPTIONS: { value: EstadoEntrega | 'TODOS'; label: string }[] = [
  { value: 'TODOS', label: 'Todos los estados' },
  { value: 'SUBIDA', label: 'Subidas' },
  { value: 'PENDIENTE', label: 'Pendientes' },
  { value: 'CORREGIDA', label: 'Corregidas' },
  { value: 'ERROR', label: 'Con errores' },
];

export const EntregasPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Selectors state
  const [selectedComisionId, setSelectedComisionId] = useState<number | null>(
    searchParams.get('comision_id') ? parseInt(searchParams.get('comision_id')!, 10) : null
  );
  const [selectedRubricaId, setSelectedRubricaId] = useState<number | null>(
    searchParams.get('rubrica_id') ? parseInt(searchParams.get('rubrica_id')!, 10) : null
  );

  const [searchTerm, setSearchTerm] = useState(searchParams.get('search') || '');
  const [estadoFilter, setEstadoFilter] = useState<EstadoEntrega | 'TODOS'>(
    (searchParams.get('estado') as EstadoEntrega) || 'TODOS'
  );
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  // Correction modal state
  const [modalEntregaId, setModalEntregaId] = useState<number | null>(null);
  const [modalAlumno, setModalAlumno] = useState('');

  // View entrega modal state
  const [viewEntregaId, setViewEntregaId] = useState<number | null>(null);
  const [viewAlumno, setViewAlumno] = useState('');
  const [viewArchivo, setViewArchivo] = useState('');

  // Download loading states
  const [downloadingPDFId, setDownloadingPDFId] = useState<number | null>(null);
  const [isBulkAction, setIsBulkAction] = useState(false);

  const page = parseInt(searchParams.get('page') || '1', 10);
  const perPage = 20;

  // Fetch comisiones (tutors see only their assigned comisiones)
  const { data: comisionesData, isLoading: isLoadingComisiones } = useComisiones({});

  // Fetch rubricas for selected comision's materia
  const selectedComision = comisionesData?.items.find(c => c.id === selectedComisionId);
  const { data: rubricasData, isLoading: isLoadingRubricas } = useRubricas(
    selectedComision?.materia_id ? { materia_id: selectedComision.materia_id } : undefined
  );
  const selectedRubrica = rubricasData?.items?.find((r) => r.id === selectedRubricaId);

  const { data, isLoading, error } = useEntregas(
    selectedComisionId && selectedRubricaId
      ? {
        comision_id: selectedComisionId,
        rubrica_id: selectedRubricaId,
        estado: estadoFilter !== 'TODOS' ? estadoFilter : undefined,
        search: searchTerm || undefined,
        page,
        per_page: perPage,
      }
      : undefined,
    { enabled: !!selectedComisionId && !!selectedRubricaId }
  );

  // Mutations
  const deleteMutation = useDeleteEntrega();
  const corregirMutation = useCorregirEntrega();
  const corregirMasivaMutation = useCorregirEntregaMasiva();
  const recorregirMutation = useRecorregirEntrega();

  // Correction data for modal
  const { data: correctionData } = useCorreccionByEntrega(modalEntregaId || 0);

  const handleSearchChange = (value: string) => {
    setSelectedIds([]);
    setSearchTerm(value);
    setSearchParams((prev) => {
      if (value) {
        prev.set('search', value);
      } else {
        prev.delete('search');
      }
      prev.set('page', '1');
      return prev;
    });
  };

  const handleEstadoChange = (value: string) => {
    setSelectedIds([]);
    const estado = value as EstadoEntrega | 'TODOS';
    setEstadoFilter(estado);
    setSearchParams((prev) => {
      if (estado !== 'TODOS') {
        prev.set('estado', estado);
      } else {
        prev.delete('estado');
      }
      prev.set('page', '1');
      return prev;
    });
  };

  const handlePageChange = (newPage: number) => {
    setSearchParams((prev) => {
      prev.set('page', newPage.toString());
      return prev;
    });
  };

  const handleDelete = async (id: number) => {
    const entrega = data?.items.find(e => e.id === id);
    const isCorregida = entrega?.estado === 'CORREGIDA';

    const message = isCorregida
      ? '⚠️ Esta entrega ya está corregida. Al eliminarla, se perderá permanentemente la entrega y su corrección. ¿Deseas continuar?'
      : '¿Estás seguro de que deseas eliminar esta entrega? Esta acción no se puede deshacer.';

    if (window.confirm(message)) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked && data?.items) {
      setSelectedIds(data.items.map((e) => e.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelectOne = (id: number, checked: boolean) => {
    if (checked) {
      setSelectedIds((prev) => [...prev, id]);
    } else {
      setSelectedIds((prev) => prev.filter((i) => i !== id));
    }
  };

  const handleCorregirSeleccionados = async () => {
    if (selectedIds.length === 0) return;

    const itemsToCorrect = data?.items.filter(
      item => selectedIds.includes(item.id) &&
        (item.estado === 'PENDIENTE' || item.estado === 'SUBIDA' || item.estado === 'ERROR')
    );

    if (!itemsToCorrect || itemsToCorrect.length === 0) {
      alert('No hay entregas pendientes de corrección en la selección.');
      return;
    }

    const ids = itemsToCorrect.map(i => i.id);

    if (confirm(`¿Confirma corregir ${ids.length} entregas seleccionadas?`)) {
      toast.loading(`Iniciando corrección de ${ids.length} ${ids.length === 1 ? 'entrega' : 'entregas'}...`, {
        duration: 3000,
      });

      try {
        await corregirMasivaMutation.mutateAsync(ids);
        setSelectedIds([]);
        toast.success(
          `Corrección completada: ${ids.length} ${ids.length === 1 ? 'entrega procesada' : 'entregas procesadas'} exitosamente`
        );
      } catch (error) {
        toast.error(`Error al corregir entregas: ${error instanceof Error ? error.message : 'Error desconocido'}`);
      }
    }
  };

  const handleRecorregir = async (entregaId: number) => {
    if (
      !confirm(
        '¿Estás seguro? Se descartará la corrección actual y se generará una nueva con la IA.'
      )
    )
      return;
    try {
      await recorregirMutation.mutateAsync(entregaId);
      toast.success('Re-corrección iniciada exitosamente');
      if (modalEntregaId === entregaId) {
        setModalEntregaId(null);
        setModalAlumno('');
      }
    } catch (e) {
      toast.error(`Error: ${e instanceof Error ? e.message : 'Error desconocido'}`);
    }
  };

  const handleDescargarPDF = async (entregaId: number) => {
    setDownloadingPDFId(entregaId);
    try {
      await descargarPDFCorreccion(entregaId);
      toast.success('PDF descargado exitosamente');
    } catch (e) {
      toast.error(
        `Error al descargar PDF: ${e instanceof Error ? e.message : 'Error desconocido'}`
      );
    } finally {
      setDownloadingPDFId(null);
    }
  };

  const handleDescargarTodosPDFs = async () => {
    if (!selectedComisionId || !selectedRubricaId) return;

    // Validar que haya entregas corregidas antes de intentar descargar
    if (corregidasCount === 0) {
      toast.error('No hay entregas corregidas para descargar');
      return;
    }

    setIsBulkAction(true);
    try {
      await descargarTodosPDFs(selectedComisionId, selectedRubricaId);
      toast.success(`ZIP con ${corregidasCount} PDFs descargado exitosamente`);
    } catch (e: any) {
      // Manejo específico de errores
      if (e.code === 'ECONNABORTED') {
        toast.error('La descarga tomó demasiado tiempo. Intenta nuevamente o contacta al administrador.');
      } else if (e.response?.status === 404) {
        toast.error('No se encontraron entregas corregidas');
      } else {
        toast.error(`Error al descargar PDFs: ${e instanceof Error ? e.message : 'Error desconocido'}`);
      }
    } finally {
      setIsBulkAction(false);
    }
  };

  /* Temporalmente deshabilitado - Exportar Excel
  const handleExportarExcel = async () => {
    if (!selectedComisionId || !selectedRubricaId) return;
    setIsBulkAction(true);
    try {
      await exportarExcel(selectedComisionId, selectedRubricaId);
      toast.success('Excel exportado exitosamente');
    } catch (e) {
      toast.error(`Error: ${e instanceof Error ? e.message : 'Error desconocido'}`);
    } finally {
      setIsBulkAction(false);
    }
  };
  */

  const getEstadoBadge = (estado: EstadoEntrega) => {
    const badges: Record<
      EstadoEntrega,
      { variant: 'success' | 'warning' | 'info' | 'destructive'; icon: string }
    > = {
      SUBIDA: { variant: 'warning', icon: '⚠️' },
      PENDIENTE: { variant: 'info', icon: '⏳' },
      CORREGIDA: { variant: 'success', icon: '✅' },
      ERROR: { variant: 'destructive', icon: '❌' },
    };

    const badge = badges[estado];
    return (
      <Badge variant={badge.variant}>
        <span className="mr-1">{badge.icon}</span>
        {estado.charAt(0) + estado.slice(1).toLowerCase()}
      </Badge>
    );
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-red-600 mb-4">Error al cargar entregas</p>
        <p className="text-sm text-gray-600 mb-6">{error.message}</p>
        <Button onClick={() => window.location.reload()}>Reintentar</Button>
      </div>
    );
  }

  const entregas = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / perPage) : 0;
  const pendientesCount = entregas.filter((e) => e.estado === 'PENDIENTE' || e.estado === 'SUBIDA' || e.estado === 'ERROR').length;
  const corregidasCount = entregas.filter((e) => e.estado === 'CORREGIDA').length;
  const allSelected = entregas.length > 0 && selectedIds.length === entregas.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Entregas</h1>
          <p className="text-sm text-gray-600 mt-1">
            Gestiona las entregas de los alumnos
          </p>
        </div>
        <div className="flex gap-2">
          {/* Bulk download actions - only visible if there are corrected entregas */}
          {selectedComisionId && selectedRubricaId && corregidasCount > 0 && (
            <>
              <Button
                variant="success"
                size="sm"
                onClick={handleDescargarTodosPDFs}
                disabled={isBulkAction}
                isLoading={isBulkAction}
              >
                <Download className="w-4 h-4" />
                {isBulkAction ? 'Generando ZIP...' : `Todos los PDFs (${corregidasCount})`}
              </Button>
              {/* Temporalmente deshabilitado - Exportar Excel
              <Button
                variant="secondary"
                size="sm"
                onClick={handleExportarExcel}
                disabled={isBulkAction}
              >
                <Download className="w-4 h-4" />
                Exportar Excel
              </Button>
              */}
            </>
          )}
          <Button
            variant="primary"
            onClick={() => setShowUploadModal(true)}
            disabled={!selectedComisionId || !selectedRubricaId}
          >
            <FileUp className="w-4 h-4" />
            Subir Entrega
          </Button>
        </div>
      </div>

      {/* Selectors: Comisión y Rúbrica */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Comisión Selector */}
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Comisión
            </label>
            <Select
              value={selectedComisionId?.toString() || ''}
              onChange={(e) => {
                const comisionId = e.target.value ? parseInt(e.target.value, 10) : null;
                setSelectedComisionId(comisionId);
                setSelectedRubricaId(null);
                setSelectedIds([]);
                setSearchParams((prev) => {
                  if (comisionId) {
                    prev.set('comision_id', comisionId.toString());
                  } else {
                    prev.delete('comision_id');
                  }
                  prev.delete('rubrica_id');
                  prev.set('page', '1');
                  return prev;
                });
              }}
              options={[
                { value: '', label: 'Selecciona una comisión' },
                ...(comisionesData?.items.map(c => ({
                  value: c.id.toString(),
                  label: `${c.nombre} - ${c.materia_nombre}`
                })) || [])
              ]}
              disabled={isLoadingComisiones}
            />
          </div>

          {/* Rúbrica Selector */}
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Rúbrica / Trabajo Práctico
            </label>
            <Select
              value={selectedRubricaId?.toString() || ''}
              onChange={(e) => {
                const rubricaId = e.target.value ? parseInt(e.target.value, 10) : null;
                setSelectedRubricaId(rubricaId);
                setSelectedIds([]);
                setSearchParams((prev) => {
                  if (rubricaId) {
                    prev.set('rubrica_id', rubricaId.toString());
                  } else {
                    prev.delete('rubrica_id');
                  }
                  prev.set('page', '1');
                  return prev;
                });
              }}
              options={[
                { value: '', label: 'Selecciona una rúbrica' },
                ...(rubricasData?.items.map(r => ({
                  value: r.id.toString(),
                  label: `${r.tipo} ${r.numero} - ${r.titulo}`
                })) || [])
              ]}
              disabled={!selectedComisionId || isLoadingRubricas}
            />
          </div>
        </div>
      </div>

      {/* Filters and Actions */}
      {selectedComisionId && selectedRubricaId && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <Input
                type="text"
                placeholder="Buscar por nombre de alumno..."
                value={searchTerm}
                onChange={(e) => handleSearchChange(e.target.value)}
                startIcon={<Search className="w-4 h-4" />}
              />
            </div>

            {/* Estado Filter */}
            <div className="w-full lg:w-64">
              <Select
                value={estadoFilter}
                onChange={(e) => handleEstadoChange(e.target.value)}
                options={ESTADO_OPTIONS}
              />
            </div>

            {/* Batch Action Button */}
            {selectedIds.length > 0 ? (
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  onClick={handleCorregirSeleccionados}
                  isLoading={corregirMasivaMutation.isPending}
                >
                  <FileCheck2 className="w-4 h-4" />
                  Corregir ({selectedIds.length})
                </Button>
              </div>
            ) : (
              pendientesCount > 0 && (
                <Button
                  variant="primary"
                  onClick={() => {
                    handleEstadoChange('PENDIENTE');
                  }}
                >
                  <FileCheck2 className="w-4 h-4" />
                  Ver Pendientes ({pendientesCount})
                </Button>
              )
            )}
          </div>
        </div>
      )}

      {/* Empty State when no selection */}
      {(!selectedComisionId || !selectedRubricaId) && (
        <EmptyState
          icon={<Upload className="w-12 h-12 text-gray-400" />}
          title="Selecciona una comisión y rúbrica"
          description="Para ver las entregas, primero debes seleccionar una comisión y el trabajo práctico (rúbrica) correspondiente"
        />
      )}

      {/* Table or Empty State */}
      {selectedComisionId && selectedRubricaId && (
        entregas.length === 0 ? (
          <EmptyState
            icon={<Upload className="w-12 h-12 text-gray-400" />}
            title="No hay entregas"
            description={
              searchTerm || estadoFilter !== 'TODOS'
                ? 'No se encontraron entregas con los filtros aplicados'
                : 'Sube la primera entrega usando el botón "Subir Entrega"'
            }
            action={
              !searchTerm && estadoFilter === 'TODOS' ? (
                <Button onClick={() => setShowUploadModal(true)}>
                  Subir Entrega
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearchTerm('');
                    setEstadoFilter('TODOS');
                    setSearchParams({});
                  }}
                >
                  Limpiar Filtros
                </Button>
              )
            }
          />
        ) : (
          <>
            {/* Table */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 w-4">
                        <Checkbox
                          checked={allSelected}
                          onChange={(e) => handleSelectAll(e.target.checked)}
                        />
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Alumno
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Archivo
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Estado
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Nota
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Fecha
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Acciones
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {entregas.map((entrega: EntregaListItem) => {
                      const isCorregida = entrega.estado === 'CORREGIDA';
                      const isPendiente = entrega.estado === 'PENDIENTE' || entrega.estado === 'SUBIDA' || entrega.estado === 'ERROR';

                      return (
                        <tr key={entrega.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <Checkbox
                              checked={selectedIds.includes(entrega.id)}
                              onChange={(e) => handleSelectOne(entrega.id, e.target.checked)}
                            />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-gray-900">
                              {entrega.alumno_nombre}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-sm text-gray-900">
                              {entrega.archivo_nombre}
                            </div>
                            <div className="text-xs text-gray-500">
                              {formatFileSize(entrega.archivo_tamanio)}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            {getEstadoBadge(entrega.estado)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">
                              {entrega.nota !== null ? (
                                <span className="font-medium">{entrega.nota}</span>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {formatDate(entrega.created_at)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <Dropdown
                              trigger={
                                <Button
                                  variant="ghost"
                                  size="sm"
                                >
                                  <MoreVertical className="w-4 h-4" />
                                </Button>
                              }
                              items={[
                                // Ver Entrega - always visible
                                {
                                  label: 'Ver Entrega',
                                  icon: <Eye className="w-4 h-4" />,
                                  onClick: () => {
                                    setViewEntregaId(entrega.id);
                                    setViewAlumno(entrega.alumno_nombre);
                                    setViewArchivo(entrega.archivo_nombre);
                                  },
                                },
                                // Actions for CORREGIDA state
                                ...(isCorregida
                                  ? [
                                    {
                                      label: 'Ver / Editar Corrección',
                                      icon: <Eye className="w-4 h-4" />,
                                      onClick: () => {
                                        setModalEntregaId(entrega.id);
                                        setModalAlumno(entrega.alumno_nombre);
                                      },
                                    },
                                    {
                                      label: 'Re-corregir',
                                      icon: <RefreshCw className="w-4 h-4" />,
                                      onClick: () => handleRecorregir(entrega.id),
                                      disabled: recorregirMutation.isPending,
                                    },
                                    {
                                      label:
                                        downloadingPDFId === entrega.id
                                          ? 'Descargando...'
                                          : 'Descargar PDF',
                                      icon: <FileText className="w-4 h-4" />,
                                      onClick: () => handleDescargarPDF(entrega.id),
                                      disabled: downloadingPDFId === entrega.id,
                                    },
                                  ]
                                  : []),
                                // Actions for PENDIENTE/SUBIDA/ERROR states
                                ...(isPendiente
                                  ? [
                                    {
                                      label: 'Corregir',
                                      icon: <FileCheck2 className="w-4 h-4" />,
                                      onClick: () => {
                                        toast.loading('Corrección iniciada en segundo plano...', {
                                          duration: 3000,
                                        });
                                        corregirMutation.mutate(entrega.id, {
                                          onSuccess: () => {
                                            toast.success(`Corrección completada para ${entrega.alumno_nombre}`);
                                          },
                                          onError: (error) => {
                                            toast.error(`Error al corregir: ${error.message}`);
                                          },
                                        });
                                      },
                                      disabled: corregirMutation.isPending,
                                    },
                                  ]
                                  : []),
                                // Delete is always available
                                {
                                  label: 'Eliminar',
                                  icon: <Trash2 className="w-4 h-4" />,
                                  onClick: () => handleDelete(entrega.id),
                                  variant: 'danger',
                                },
                              ]}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-t border-gray-200">
                  <div className="text-sm text-gray-700">
                    Mostrando {(page - 1) * perPage + 1} -{' '}
                    {Math.min(page * perPage, data?.total || 0)} de {data?.total}{' '}
                    entregas
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page === 1}
                      onClick={() => handlePageChange(page - 1)}
                    >
                      Anterior
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => handlePageChange(page + 1)}
                    >
                      Siguiente
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </>
        )
      )}

      {/* Upload Modal */}
      {showUploadModal && selectedComisionId && selectedRubricaId && (
        <CargaEntregaModal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          comisionId={selectedComisionId}
          rubricaId={selectedRubricaId}
        />
      )}

      {/* Correction View/Edit Modal */}
      {modalEntregaId && correctionData && (
        <CorreccionViewEditModal
          correccion={correctionData}
          alumno={modalAlumno}
          trabajoNombre={
            selectedRubrica
              ? `${selectedRubrica.tipo} ${selectedRubrica.numero} - ${selectedRubrica.titulo}`
              : ''
          }
          isOpen={true}
          onClose={() => {
            setModalEntregaId(null);
            setModalAlumno('');
          }}
        />
      )}

      {/* View Entrega Modal */}
      {viewEntregaId && (
        <EntregaViewModal
          entregaId={viewEntregaId}
          alumno={viewAlumno}
          archivoNombre={viewArchivo}
          isOpen={true}
          onClose={() => {
            setViewEntregaId(null);
            setViewAlumno('');
            setViewArchivo('');
          }}
        />
      )}
    </div>
  );
};
