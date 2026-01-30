// features/entregas/pages/EntregasPage.tsx
/**
 * EntregasPage - Main page for managing student submissions.
 *
 * Displays a table of entregas with filters, search, and actions.
 * Tutors can view, upload, and manage student submissions.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md section 4.2
 */

import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useEntregas, useDeleteEntrega, useCorregirEntregaMasiva, useCorregirEntrega } from '../hooks';
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
  PackageOpen,
} from 'lucide-react';
import type { EstadoEntrega, EntregaListItem } from '../types';

interface EntregasPageProps {
  comisionId: number;
  rubricaId: number;
}

const ESTADO_OPTIONS: { value: EstadoEntrega | 'TODOS'; label: string }[] = [
  { value: 'TODOS', label: 'Todos los estados' },
  { value: 'SUBIDA', label: 'Subidas' },
  { value: 'PENDIENTE', label: 'Pendientes' },
  { value: 'CORREGIDA', label: 'Corregidas' },
  { value: 'ERROR', label: 'Con errores' },
];

export const EntregasPage = ({ comisionId, rubricaId }: EntregasPageProps) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchTerm, setSearchTerm] = useState(searchParams.get('search') || '');
  const [estadoFilter, setEstadoFilter] = useState<EstadoEntrega | 'TODOS'>(
    (searchParams.get('estado') as EstadoEntrega) || 'TODOS'
  );
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showBulkUploadModal, setShowBulkUploadModal] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const page = parseInt(searchParams.get('page') || '1', 10);
  const perPage = 20;

  const { data, isLoading, error } = useEntregas({
    comision_id: comisionId,
    rubrica_id: rubricaId,
    estado: estadoFilter !== 'TODOS' ? estadoFilter : undefined,
    search: searchTerm || undefined,
    page,
    per_page: perPage,
  });

  const deleteMutation = useDeleteEntrega();
  const corregirMutation = useCorregirEntrega();
  const corregirMasivaMutation = useCorregirEntregaMasiva();

  const handleSearchChange = (value: string) => {
    setSelectedIds([]);
    setSearchTerm(value);
    setSearchParams((prev) => {
      if (value) {
        prev.set('search', value);
      } else {
        prev.delete('search');
      }
      prev.set('page', '1'); // Reset to first page
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
      prev.set('page', '1'); // Reset to first page
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
    if (window.confirm('¿Estás seguro de que deseas eliminar esta entrega?')) {
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

    // Filter only those that can be corrected (PENDIENTE or SUBIDA or ERROR)
    // Note: 'ERROR' items might be re-correctable
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
      try {
        await corregirMasivaMutation.mutateAsync(ids);
        setSelectedIds([]);
      } catch (e) {
        console.error(e);
        alert('Error al iniciar corrección masiva');
      }
    }
  };

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
  const pendientesCount = entregas.filter((e) => e.estado === 'PENDIENTE').length;

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
          <Button
            variant="secondary"
            onClick={() => setShowBulkUploadModal(true)}
          >
            <PackageOpen className="w-4 h-4" />
            Subir Lote
          </Button>
          <Button
            variant="primary"
            onClick={() => setShowUploadModal(true)}
          >
            <FileUp className="w-4 h-4" />
            Subir Entrega
          </Button>
        </div>
      </div>

      {/* Filters and Actions */}
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

      {/* Table or Empty State */}
      {entregas.length === 0 ? (
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
                  {entregas.map((entrega: EntregaListItem) => (
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
                            {
                              label: 'Ver Detalle',
                              icon: <Eye className="w-4 h-4" />,
                              onClick: () => {
                                console.log('Ver detalle', entrega.id);
                              },
                            },
                            {
                              label: 'Corregir',
                              icon: <FileCheck2 className="w-4 h-4" />,
                              onClick: () => corregirMutation.mutate(entrega.id),
                              disabled: entrega.estado !== 'PENDIENTE' && entrega.estado !== 'SUBIDA',
                            },
                            ...(entrega.tiene_correccion
                              ? [
                                {
                                  label: 'Ver Corrección',
                                  icon: <FileCheck2 className="w-4 h-4" />,
                                  onClick: () => {
                                    console.log('Ver corrección', entrega.id);
                                    // Open modal (task 6.19)
                                  },
                                },
                              ]
                              : []),
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
                  ))}
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
      )}

      {/* Modals (Placeholders for now - will be implemented in task 6.17) */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-4">Subir Entrega</h3>
            <p className="text-sm text-gray-600 mb-4">
              Componente CargaEntregaModal será implementado en la tarea 6.17
            </p>
            <Button onClick={() => setShowUploadModal(false)}>Cerrar</Button>
          </div>
        </div>
      )}

      {showBulkUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold mb-4">Subir Lote</h3>
            <p className="text-sm text-gray-600 mb-4">
              Componente CargaEntregaModal (modo masivo) será implementado en la
              tarea 6.17
            </p>
            <Button onClick={() => setShowBulkUploadModal(false)}>Cerrar</Button>
          </div>
        </div>
      )}
    </div>
  );
};
