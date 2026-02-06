// features/correcciones/pages/CorreccionesPage.tsx
/**
 * CorreccionesPage - Revisión y edición de correcciones generadas por IA.
 *
 * Permite al Tutor ver las entregas corregidas, abrir el modal de edición,
 * re-corregir, descargar PDFs individuales o en lote, y exportar notas a Excel.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md sección 4.2 (tabla de entregas + acciones)
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md módulos 8, 9
 */

import { useState } from 'react';
import toast from 'react-hot-toast';
import { useEntregas } from '@/features/entregas/hooks';
import { useComisiones } from '@/features/comisiones/hooks';
import { useRubricas } from '@/features/rubricas/hooks';
import { useCorreccionByEntrega, useRecorregirEntrega } from '../hooks/useCorrecciones';
import {
  descargarPDFCorreccion,
  descargarTodosPDFs,
  exportarExcel,
} from '../services/correcciones-service';
import CorreccionDetailModal from '../components/CorreccionDetailModal';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Select } from '@/shared/components/ui/Select';
import { Badge } from '@/shared/components/ui/Badge';
import { Spinner } from '@/shared/components/ui/Spinner';
import { EmptyState } from '@/shared/components/ui/EmptyState';
import { Dropdown } from '@/shared/components/ui/Dropdown';
import {
  Search,
  MoreVertical,
  Eye,
  RefreshCw,
  FileText,
  Download,
  ClipboardCheck,
} from 'lucide-react';
import type { EntregaListItem } from '@/features/entregas/types';

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  });
};

export const CorreccionesPage = () => {
  // Selectors
  const [selectedComisionId, setSelectedComisionId] = useState<number | null>(null);
  const [selectedRubricaId, setSelectedRubricaId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const perPage = 20;

  // Modal
  const [modalEntregaId, setModalEntregaId] = useState<number | null>(null);
  const [modalAlumno, setModalAlumno] = useState('');

  // Loading flags para descargas
  const [downloadingPDFId, setDownloadingPDFId] = useState<number | null>(null);
  const [isBulkAction, setIsBulkAction] = useState(false);

  // --- Data fetching ---
  const { data: comisionesData, isLoading: isLoadingComisiones } = useComisiones({});

  const selectedComision = comisionesData?.items.find((c) => c.id === selectedComisionId);
  const { data: rubricasData, isLoading: isLoadingRubricas } = useRubricas(
    selectedComision?.materia_id ? { materia_id: selectedComision.materia_id } : undefined
  );
  const selectedRubrica = rubricasData?.items?.find((r) => r.id === selectedRubricaId);

  // Entregas filtradas por estado CORREGIDA
  const { data, isLoading, error } = useEntregas(
    selectedComisionId && selectedRubricaId
      ? {
          comision_id: selectedComisionId,
          rubrica_id: selectedRubricaId,
          estado: 'CORREGIDA',
          search: searchTerm || undefined,
          page,
          per_page: perPage,
        }
      : undefined,
    { enabled: !!selectedComisionId && !!selectedRubricaId }
  );

  // Corrección para el modal (se habilita solo cuando hay entrega seleccionada)
  const { data: correctionData } = useCorreccionByEntrega(modalEntregaId || 0);
  const recorregirMutation = useRecorregirEntrega();

  // --- Handlers ---
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
      // Cerrar modal si estaba abierto para esta entrega
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
    setIsBulkAction(true);
    try {
      await descargarTodosPDFs(selectedComisionId, selectedRubricaId);
    } catch (e) {
      toast.error(`Error: ${e instanceof Error ? e.message : 'Error desconocido'}`);
    } finally {
      setIsBulkAction(false);
    }
  };

  const handleExportarExcel = async () => {
    if (!selectedComisionId || !selectedRubricaId) return;
    setIsBulkAction(true);
    try {
      await exportarExcel(selectedComisionId, selectedRubricaId);
    } catch (e) {
      toast.error(`Error: ${e instanceof Error ? e.message : 'Error desconocido'}`);
    } finally {
      setIsBulkAction(false);
    }
  };

  // --- Derived ---
  const entregas = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  // --- Render ---
  return (
    <div className="space-y-6">
      {/* Header con acciones en lote */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Correcciones</h1>
          <p className="text-sm text-gray-600 mt-1">
            Revisión y edición de correcciones generadas por IA
          </p>
        </div>
        {selectedComisionId && selectedRubricaId && entregas.length > 0 && (
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDescargarTodosPDFs}
              disabled={isBulkAction}
            >
              <Download className="w-4 h-4" />
              Todos los PDFs
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleExportarExcel}
              disabled={isBulkAction}
            >
              <Download className="w-4 h-4" />
              Exportar Excel
            </Button>
          </div>
        )}
      </div>

      {/* Selectores + búsqueda */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Comisión */}
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Comisión</label>
            <Select
              value={selectedComisionId?.toString() || ''}
              onChange={(e) => {
                setSelectedComisionId(e.target.value ? parseInt(e.target.value, 10) : null);
                setSelectedRubricaId(null);
                setPage(1);
              }}
              options={[
                { value: '', label: 'Selecciona una comisión' },
                ...(comisionesData?.items.map((c) => ({
                  value: c.id.toString(),
                  label: `${c.nombre} - ${c.materia_nombre}`,
                })) || []),
              ]}
              disabled={isLoadingComisiones}
            />
          </div>

          {/* Rúbrica */}
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Rúbrica / Trabajo
            </label>
            <Select
              value={selectedRubricaId?.toString() || ''}
              onChange={(e) => {
                setSelectedRubricaId(e.target.value ? parseInt(e.target.value, 10) : null);
                setPage(1);
              }}
              options={[
                { value: '', label: 'Selecciona una rúbrica' },
                ...(rubricasData?.items.map((r) => ({
                  value: r.id.toString(),
                  label: `${r.tipo} ${r.numero} - ${r.nombre}`,
                })) || []),
              ]}
              disabled={!selectedComisionId || isLoadingRubricas}
            />
          </div>

          {/* Búsqueda */}
          <div className="flex-1 lg:max-w-xs">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Buscar alumno
            </label>
            <Input
              type="text"
              placeholder="Nombre..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
              startIcon={<Search className="w-4 h-4" />}
            />
          </div>
        </div>
      </div>

      {/* Estado vacío: sin selección */}
      {(!selectedComisionId || !selectedRubricaId) && (
        <EmptyState
          icon={<ClipboardCheck className="w-12 h-12 text-gray-400" />}
          title="Selecciona una comisión y rúbrica"
          description="Para ver las correcciones, selecciona la comisión y el trabajo práctico correspondiente"
        />
      )}

      {/* Contenido principal: carga / error / tabla */}
      {selectedComisionId &&
        selectedRubricaId &&
        (isLoading ? (
          <div className="flex justify-center items-center py-12">
            <Spinner size="lg" />
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-600 mb-2">Error al cargar correcciones</p>
            <p className="text-sm text-gray-600">{error.message}</p>
          </div>
        ) : entregas.length === 0 ? (
          <EmptyState
            icon={<ClipboardCheck className="w-12 h-12 text-gray-400" />}
            title="No hay correcciones"
            description={
              searchTerm
                ? 'No se encontraron correcciones con ese filtro'
                : 'No hay entregas corregidas para esta comisión y rúbrica'
            }
          />
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Alumno
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Nota
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Estado
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
                        <div className="text-sm font-medium text-gray-900">
                          {entrega.alumno_nombre}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm font-semibold text-gray-900">{entrega.nota}</span>
                        <span className="text-sm text-gray-400"> /100</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant="success">✅ Corregida</Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(entrega.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <Dropdown
                          trigger={
                            <Button variant="ghost" size="sm">
                              <MoreVertical className="w-4 h-4" />
                            </Button>
                          }
                          items={[
                            {
                              label: 'Ver / Editar',
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
                          ]}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Paginación */}
            {totalPages > 1 && (
              <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-t border-gray-200">
                <div className="text-sm text-gray-700">
                  Página {page} de {totalPages}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Anterior
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Siguiente
                  </Button>
                </div>
              </div>
            )}
          </div>
        ))}

      {/* Modal de detalle / edición de corrección */}
      {modalEntregaId && correctionData && (
        <CorreccionDetailModal
          correccion={correctionData}
          alumno={modalAlumno}
          trabajoNombre={
            selectedRubrica
              ? `${selectedRubrica.tipo} ${selectedRubrica.numero} - ${selectedRubrica.nombre}`
              : ''
          }
          isOpen={true}
          onClose={() => {
            setModalEntregaId(null);
            setModalAlumno('');
          }}
        />
      )}
    </div>
  );
};
