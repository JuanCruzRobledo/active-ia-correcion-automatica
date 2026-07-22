// features/correcciones/components/CorreccionViewEditModal.tsx
/**
 * Professional modal component for viewing and editing corrections with excellent UX/UI.
 *
 * Features:
 * - Toggle between View (read-only) and Edit modes
 * - Collapsible/expandable sections (accordion)
 * - Visual hierarchy with nota final prominently displayed
 * - Clear visual states for criterios (OK/WARNING/ERROR)
 * - Responsive design with smooth transitions
 *
 * Priority visual hierarchy (top to bottom):
 * 1. Nota final - Always visible, highlighted (non-collapsible)
 * 2. Criterios evaluados - Collapsible cards with visual states
 * 3. Fortalezas - Collapsible bullet list
 * 4. Recomendaciones - Collapsible numbered list
 * 5. Comentario general - Collapsible textarea
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md - Modal de Detalle/Edición
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md - HU-EDIT-01
 */

import { useState, useEffect } from 'react';
import {
  X,
  Eye,
  Pencil,
  Calculator,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Plus,
  Lightbulb,
  ListChecks,
  MessageSquare,
} from 'lucide-react';
import { Modal } from '../../../shared/components/ui/Modal';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Select } from '../../../shared/components/ui/Select';
import { Badge } from '../../../shared/components/ui/Badge';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '../../../shared/components/ui/Accordion';
import { useUpdateCorreccion } from '../hooks/useCorrecciones';
import { cn } from '../../../shared/utils/cn';
import type { Correccion, CriterioEvaluado, EstadoCriterio } from '../types';

interface CorreccionViewEditModalProps {
  /** Corrección a mostrar/editar */
  correccion: Correccion;
  /** Nombre del alumno */
  alumno: string;
  /** Nombre del trabajo (ej: "TP1 - Listas en Python") */
  trabajoNombre: string;
  /** Estado abierto/cerrado */
  isOpen: boolean;
  /** Callback al cerrar */
  onClose: () => void;
}

/**
 * Modal for viewing and editing corrections with professional UX/UI.
 *
 * Supports two modes:
 * - View mode: Read-only display with disabled inputs
 * - Edit mode: Full editing capabilities with validation
 */
export default function CorreccionViewEditModal({
  correccion,
  alumno,
  trabajoNombre,
  isOpen,
  onClose,
}: CorreccionViewEditModalProps) {
  // Mode toggle: 'view' or 'edit'
  const [mode, setMode] = useState<'view' | 'edit'>('view');

  // Form state (editable data)
  // Convert nota from string to number (backend returns Decimal as string)
  const [nota, setNota] = useState(Number(correccion.nota));
  // Convert puntaje fields to numbers in criterios
  // Fallback to empty array if criterios is undefined
  const [criterios, setCriterios] = useState<CriterioEvaluado[]>(
    (correccion.criterios || []).map(c => ({
      ...c,
      puntaje_obtenido: Number(c.puntaje_obtenido),
      puntaje_maximo: Number(c.puntaje_maximo),
    }))
  );
  const [fortalezas, setFortalezas] = useState<string[]>(
    correccion.fortalezas
  );
  const [recomendaciones, setRecomendaciones] = useState<string[]>(
    correccion.recomendaciones
  );
  const [comentarioGeneral, setComentarioGeneral] = useState(
    correccion.comentario_general
  );

  // CD and penalties state
  const [cdAplicada, setCdAplicada] = useState<string | null>(
    correccion.condicion_desaprobacion_aplicada
  );
  const [penalizaciones, setPenalizaciones] = useState<string[]>(
    correccion.penalizaciones_aplicadas || []
  );

  // Temporary inputs for adding new items
  const [nuevaFortaleza, setNuevaFortaleza] = useState('');
  const [nuevaRecomendacion, setNuevaRecomendacion] = useState('');

  // Mutation hook for saving changes
  const updateMutation = useUpdateCorreccion();

  // Reset local state when correccion changes
  useEffect(() => {
    setNota(Number(correccion.nota));
    setCriterios((correccion.criterios || []).map(c => ({
      ...c,
      puntaje_obtenido: Number(c.puntaje_obtenido),
      puntaje_maximo: Number(c.puntaje_maximo),
    })));
    setFortalezas(correccion.fortalezas || []);
    setRecomendaciones(correccion.recomendaciones || []);
    setComentarioGeneral(correccion.comentario_general || '');
    setCdAplicada(correccion.condicion_desaprobacion_aplicada);
    setPenalizaciones(correccion.penalizaciones_aplicadas || []);
    setMode('view'); // Reset to view mode
  }, [correccion]);

  /**
   * Recalculates nota by summing criteria and applying CD/penalties.
   */
  const handleRecalcularNota = () => {
    const sumaCriterios = criterios.reduce(
      (sum, c) => sum + c.puntaje_obtenido,
      0
    );
    setNota(sumaCriterios);
  };

  /**
   * Updates a specific criterio field.
   */
  const handleCriterioChange = (
    index: number,
    field: keyof CriterioEvaluado,
    value: string | number
  ) => {
    const newCriterios = [...criterios];
    newCriterios[index] = { ...newCriterios[index], [field]: value };
    setCriterios(newCriterios);
  };

  /**
   * Adds a new fortaleza to the list.
   */
  const handleAgregarFortaleza = () => {
    if (nuevaFortaleza.trim()) {
      setFortalezas([...fortalezas, nuevaFortaleza.trim()]);
      setNuevaFortaleza('');
    }
  };

  /**
   * Removes a fortaleza by index.
   */
  const handleEliminarFortaleza = (index: number) => {
    setFortalezas(fortalezas.filter((_, i) => i !== index));
  };

  /**
   * Adds a new recomendacion to the list.
   */
  const handleAgregarRecomendacion = () => {
    if (nuevaRecomendacion.trim()) {
      setRecomendaciones([...recomendaciones, nuevaRecomendacion.trim()]);
      setNuevaRecomendacion('');
    }
  };

  /**
   * Removes a recomendacion by index.
   */
  const handleEliminarRecomendacion = (index: number) => {
    setRecomendaciones(recomendaciones.filter((_, i) => i !== index));
  };

  /**
   * Saves changes by sending to backend.
   */
  const handleGuardar = () => {
    const sumaCriterios = criterios.reduce((sum, c) => sum + c.puntaje_obtenido, 0);
    updateMutation.mutate(
      {
        correccionId: correccion.id,
        data: {
          nota,
          nota_antes_penalizaciones: sumaCriterios,
          condicion_desaprobacion_aplicada: cdAplicada || null,
          penalizaciones_aplicadas: penalizaciones,
          criterios,
          fortalezas,
          recomendaciones,
          comentario_general: comentarioGeneral,
        },
      },
      {
        onSuccess: () => {
          setMode('view'); // Return to view mode after saving
        },
      }
    );
  };

  /**
   * Cancels changes and returns to view mode.
   */
  const handleCancelar = () => {
    // Reset to original values
    setNota(Number(correccion.nota));
    setCriterios((correccion.criterios || []).map(c => ({
      ...c,
      puntaje_obtenido: Number(c.puntaje_obtenido),
      puntaje_maximo: Number(c.puntaje_maximo),
    })));
    setFortalezas(correccion.fortalezas || []);
    setRecomendaciones(correccion.recomendaciones || []);
    setComentarioGeneral(correccion.comentario_general || '');
    setCdAplicada(correccion.condicion_desaprobacion_aplicada);
    setPenalizaciones(correccion.penalizaciones_aplicadas || []);
    setMode('view');
  };

  /**
   * Closes modal and resets state.
   */
  const handleClose = () => {
    handleCancelar(); // Reset state first
    onClose();
  };

  /**
   * Gets color class based on nota value.
   */
  const getNotaColor = (notaValue: number) => {
    if (notaValue >= 80) return 'text-success';
    if (notaValue >= 60) return 'text-warning';
    return 'text-destructive';
  };

  const isViewMode = mode === 'view';

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="2xl" title={`Corrección: ${alumno}`}>
      {/* Info and Mode Toggle - No scrollable */}
      <div className="flex items-center justify-between border-b border-border pb-4 mb-4 -mt-6">
        <p className="text-sm text-muted-foreground">
          {trabajoNombre}
        </p>

        {/* Mode Toggle Button */}
        <Button
          variant={isViewMode ? 'outline' : 'primary'}
          size="sm"
          onClick={() => setMode(isViewMode ? 'edit' : 'view')}
          className="gap-2"
        >
          {isViewMode ? (
            <>
              <Pencil className="h-4 w-4" />
              Editar
            </>
          ) : (
            <>
              <Eye className="h-4 w-4" />
              Ver
            </>
          )}
        </Button>
      </div>

      {/* Content - Scrollable */}
      <div className="space-y-6 max-h-[calc(100vh-22rem)] overflow-y-auto pr-2">
        {/* 1. NOTA FINAL - Compact and prominent */}
        <section className="bg-gradient-to-br from-muted/80 to-muted/40 rounded-lg p-4 border border-border">
          <div className="flex items-center justify-between gap-4">
            {/* Left: Label and Recalcular button */}
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide">
                Nota Final
              </h3>
              {!isViewMode && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRecalcularNota}
                  className="gap-1.5 text-xs"
                >
                  <Calculator className="h-3.5 w-3.5" />
                  Recalcular
                </Button>
              )}
            </div>

            {/* Right: Nota display */}
            <div className="flex items-baseline gap-2">
              {isViewMode ? (
                <div className={cn('text-4xl font-bold', getNotaColor(nota))}>
                  {nota.toFixed(1)}
                </div>
              ) : (
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={nota}
                  onChange={(e) => setNota(Number(e.target.value))}
                  className={cn(
                    'text-4xl font-bold text-center w-28 bg-transparent',
                    'border-b-2 border-border focus:border-accent focus:outline-none',
                    'transition-colors',
                    getNotaColor(nota)
                  )}
                />
              )}
              <span className="text-sm text-muted-foreground">/ 100</span>
            </div>
          </div>

          {/* Merit score (nota_antes_penalizaciones) */}
          {correccion.nota_antes_penalizaciones != null &&
            correccion.nota_antes_penalizaciones !== Number(correccion.nota) && (
            <div className="mt-3 pt-3 border-t border-border/50 text-sm text-muted-foreground">
              Puntaje por mérito: <span className="font-medium text-foreground">{Number(correccion.nota_antes_penalizaciones).toFixed(1)}</span> / 100
            </div>
          )}
        </section>

        {/* Condición de desaprobación alert */}
        {cdAplicada && (
          <section className="rounded-lg border-2 border-destructive/50 bg-destructive/10 p-4">
            <div className="flex items-start gap-3">
              <XCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-destructive text-sm">
                    Nota limitada por incumplimiento de requisitos
                  </h4>
                  {!isViewMode && (
                    <button
                      onClick={() => {
                        setCdAplicada(null);
                        handleRecalcularNota();
                      }}
                      className="text-destructive hover:text-destructive/70 transition-colors"
                      title="Quitar condición de desaprobación"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <ul className="text-sm text-foreground mt-2 space-y-1">
                  <li className="flex items-start gap-2">
                    <span className="text-destructive mt-1">•</span>
                    <span>{correccion.condicion_desaprobacion_descripcion || cdAplicada}</span>
                  </li>
                </ul>
                {isViewMode && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Esto limita la nota máxima alcanzable a{' '}
                    <span className="font-medium">{Number(correccion.nota).toFixed(1)}</span>.
                    {correccion.nota_antes_penalizaciones != null && (
                      <> Tu puntaje obtenido por mérito fue{' '}
                      <span className="font-medium">{Number(correccion.nota_antes_penalizaciones).toFixed(1)}</span>/100.</>
                    )}
                  </p>
                )}
              </div>
            </div>
          </section>
        )}

        {/* Penalizaciones alert */}
        {penalizaciones && penalizaciones.length > 0 && (
          <section className="rounded-lg border-2 border-warning/50 bg-warning/10 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h4 className="font-semibold text-warning text-sm">
                  Penalizaciones aplicadas
                </h4>
                <ul className="text-sm text-foreground mt-2 space-y-1">
                  {penalizaciones.map((penId) => {
                    const penInfo = correccion.penalizaciones_descripciones?.find(p => p.id === penId);
                    return (
                      <li key={penId} className="flex items-center justify-between gap-2">
                        <div className="flex items-start gap-2 flex-1">
                          <span className="text-warning mt-1">•</span>
                          <span>
                            {penInfo?.descripcion || penId}
                            {penInfo && penInfo.descuento_porcentaje > 0 && (
                              <span className="text-muted-foreground"> (descuento del {penInfo.descuento_porcentaje}%)</span>
                            )}
                          </span>
                        </div>
                        {!isViewMode && (
                          <button
                            onClick={() => setPenalizaciones(penalizaciones.filter(id => id !== penId))}
                            className="text-warning hover:text-warning/70 transition-colors flex-shrink-0"
                            title="Quitar penalización"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {isViewMode && correccion.nota_antes_penalizaciones != null && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Puntaje antes de penalizaciones:{' '}
                    <span className="font-medium">{Number(correccion.nota_antes_penalizaciones).toFixed(1)}</span>/100
                    {' → '}Nota final: <span className="font-medium">{Number(correccion.nota).toFixed(1)}</span>/100
                  </p>
                )}
              </div>
            </div>
          </section>
        )}

        {/* 2. CRITERIOS EVALUADOS - Collapsible with visual states */}
        <Accordion defaultValue={['criterios']}>
          <AccordionItem value="criterios">
            <AccordionTrigger
              value="criterios"
              icon={<ListChecks className="h-5 w-5" />}
              badge={
                <Badge variant="outline" className="ml-2">
                  {criterios.length} criterios
                </Badge>
              }
            >
              Criterios de Evaluación
            </AccordionTrigger>
            <AccordionContent value="criterios">
              {criterios.length > 0 ? (
                <div className="space-y-3">
                  {criterios.map((criterio, index) => (
                    <CriterioCard
                      key={criterio.id}
                      criterio={criterio}
                      isViewMode={isViewMode}
                      onChange={(field, value) =>
                        handleCriterioChange(index, field, value)
                      }
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 bg-muted/30 rounded-lg border border-dashed border-border">
                  <ListChecks className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
                  <p className="text-sm font-medium text-foreground mb-1">
                    No hay criterios de evaluación
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Esta corrección no tiene criterios definidos. Contacta al administrador.
                  </p>
                </div>
              )}
            </AccordionContent>
          </AccordionItem>

          {/* 3. FORTALEZAS - Collapsible bullet list */}
          <AccordionItem value="fortalezas">
            <AccordionTrigger
              value="fortalezas"
              icon={<CheckCircle2 className="h-5 w-5" />}
              badge={
                <Badge variant="success" className="ml-2">
                  {fortalezas.length}
                </Badge>
              }
            >
              Fortalezas
            </AccordionTrigger>
            <AccordionContent value="fortalezas">
              {!isViewMode && (
                <div className="flex gap-2 mb-4">
                  <Input
                    type="text"
                    value={nuevaFortaleza}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNuevaFortaleza(e.target.value)
                    }
                    onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAgregarFortaleza();
                      }
                    }}
                    placeholder="Agregar nueva fortaleza..."
                    className="flex-1"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAgregarFortaleza}
                    disabled={!nuevaFortaleza.trim()}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              )}

              {fortalezas.length > 0 ? (
                <ul className="space-y-2">
                  {fortalezas.map((fortaleza, index) => (
                    <li
                      key={fortaleza}
                      className="flex items-start justify-between bg-success/5 rounded-md p-3 border border-success/20"
                    >
                      <span className="flex items-start gap-2 flex-1 text-sm text-foreground">
                        <CheckCircle2 className="h-4 w-4 text-success mt-0.5 flex-shrink-0" />
                        {fortaleza}
                      </span>
                      {!isViewMode && (
                        <button
                          onClick={() => handleEliminarFortaleza(index)}
                          className="text-muted-foreground hover:text-destructive transition-colors ml-2"
                          aria-label="Eliminar fortaleza"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No hay fortalezas registradas.
                </p>
              )}
            </AccordionContent>
          </AccordionItem>

          {/* 4. RECOMENDACIONES - Collapsible numbered list */}
          <AccordionItem value="recomendaciones">
            <AccordionTrigger
              value="recomendaciones"
              icon={<Lightbulb className="h-5 w-5" />}
              badge={
                <Badge variant="warning" className="ml-2">
                  {recomendaciones.length}
                </Badge>
              }
            >
              Recomendaciones
            </AccordionTrigger>
            <AccordionContent value="recomendaciones">
              {!isViewMode && (
                <div className="flex gap-2 mb-4">
                  <Input
                    type="text"
                    value={nuevaRecomendacion}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setNuevaRecomendacion(e.target.value)
                    }
                    onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAgregarRecomendacion();
                      }
                    }}
                    placeholder="Agregar nueva recomendación..."
                    className="flex-1"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAgregarRecomendacion}
                    disabled={!nuevaRecomendacion.trim()}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              )}

              {recomendaciones.length > 0 ? (
                <ol className="space-y-2">
                  {recomendaciones.map((recomendacion, index) => (
                    <li
                      key={recomendacion}
                      className="flex items-start justify-between bg-warning/5 rounded-md p-3 border border-warning/20"
                    >
                      <span className="flex items-start gap-3 flex-1 text-sm text-foreground">
                        <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-warning/20 text-warning text-xs font-semibold flex-shrink-0">
                          {index + 1}
                        </span>
                        {recomendacion}
                      </span>
                      {!isViewMode && (
                        <button
                          onClick={() => handleEliminarRecomendacion(index)}
                          className="text-muted-foreground hover:text-destructive transition-colors ml-2"
                          aria-label="Eliminar recomendación"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No hay recomendaciones registradas.
                </p>
              )}
            </AccordionContent>
          </AccordionItem>

          {/* 5. COMENTARIO GENERAL - Collapsible textarea */}
          <AccordionItem value="comentario">
            <AccordionTrigger
              value="comentario"
              icon={<MessageSquare className="h-5 w-5" />}
            >
              Comentario General
            </AccordionTrigger>
            <AccordionContent value="comentario">
              <textarea
                value={comentarioGeneral}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                  setComentarioGeneral(e.target.value)
                }
                disabled={isViewMode}
                rows={4}
                className={cn(
                  'w-full px-3 py-2 rounded-md border border-input bg-background text-sm',
                  'focus:outline-none focus:ring-2 focus:ring-ring',
                  'transition-colors',
                  isViewMode && 'bg-muted/30 cursor-not-allowed'
                )}
                placeholder={
                  isViewMode
                    ? 'Sin comentario general'
                    : 'Escribe un comentario general para el alumno...'
                }
              />
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      {/* Footer - Only visible in Edit mode */}
      {!isViewMode && (
        <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-6">
          <Button variant="ghost" onClick={handleCancelar}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            onClick={handleGuardar}
            disabled={updateMutation.isPending}
            isLoading={updateMutation.isPending}
          >
            Guardar Cambios
          </Button>
        </div>
      )}
    </Modal>
  );
}

/**
 * Card component for displaying and editing a single criterio.
 */
interface CriterioCardProps {
  criterio: CriterioEvaluado;
  isViewMode: boolean;
  onChange: (field: keyof CriterioEvaluado, value: string | number) => void;
}

function CriterioCard({ criterio, isViewMode, onChange }: CriterioCardProps) {
  // Estado options for select
  const estadoOptions: { value: EstadoCriterio; label: string }[] = [
    { value: 'OK', label: 'OK' },
    { value: 'WARNING', label: 'Warning' },
    { value: 'ERROR', label: 'Error' },
  ];

  // Generate score options (0 to puntaje_maximo)
  const puntajeOptions = Array.from(
    { length: criterio.puntaje_maximo + 1 },
    (_, i) => ({
      value: i.toString(),
      label: i.toString(),
    })
  );

  // Get estado icon and color
  const getEstadoConfig = (estado: EstadoCriterio) => {
    switch (estado) {
      case 'OK':
        return {
          icon: CheckCircle2,
          variant: 'success' as const,
          bgClass: 'bg-success/10',
          borderClass: 'border-success/30',
        };
      case 'WARNING':
        return {
          icon: AlertTriangle,
          variant: 'warning' as const,
          bgClass: 'bg-warning/10',
          borderClass: 'border-warning/30',
        };
      case 'ERROR':
        return {
          icon: XCircle,
          variant: 'destructive' as const,
          bgClass: 'bg-destructive/10',
          borderClass: 'border-destructive/30',
        };
    }
  };

  const estadoConfig = getEstadoConfig(criterio.estado);
  const EstadoIcon = estadoConfig.icon;

  return (
    <div
      className={cn(
        'rounded-lg border p-4 space-y-3 transition-all',
        estadoConfig.bgClass,
        estadoConfig.borderClass
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <EstadoIcon className="h-5 w-5" />
          <h4 className="font-medium text-foreground">{criterio.nombre}</h4>
        </div>
        <Badge variant={estadoConfig.variant}>{criterio.estado}</Badge>
      </div>

      {/* Puntaje and Estado controls */}
      <div className="grid grid-cols-2 gap-3">
        {/* Puntaje */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Puntaje
          </label>
          {isViewMode ? (
            <div className="text-lg font-semibold">
              {criterio.puntaje_obtenido} / {criterio.puntaje_maximo}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Select
                value={criterio.puntaje_obtenido.toString()}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                  onChange('puntaje_obtenido', Number(e.target.value))
                }
                options={puntajeOptions}
                className="flex-1"
              />
              <span className="text-sm text-muted-foreground">
                / {criterio.puntaje_maximo}
              </span>
            </div>
          )}
        </div>

        {/* Estado */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Estado
          </label>
          {isViewMode ? (
            <div className="flex items-center gap-2 text-sm">
              <EstadoIcon className="h-4 w-4" />
              {criterio.estado}
            </div>
          ) : (
            <Select
              value={criterio.estado}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                onChange('estado', e.target.value as EstadoCriterio)
              }
              options={estadoOptions}
            />
          )}
        </div>
      </div>

      {/* Feedback */}
      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5">
          Feedback
        </label>
        <textarea
          value={criterio.feedback}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
            onChange('feedback', e.target.value)
          }
          disabled={isViewMode}
          rows={3}
          className={cn(
            'w-full px-3 py-2 rounded-md border border-input bg-background text-sm',
            'focus:outline-none focus:ring-2 focus:ring-ring',
            'transition-colors',
            isViewMode && 'bg-muted/30 cursor-not-allowed'
          )}
          placeholder={
            isViewMode ? 'Sin feedback' : 'Feedback específico para este criterio...'
          }
        />
      </div>

      {/* Desglose por subcriterio (rúbricas schema_version >= 2). Tolerante a su
          ausencia: correcciones viejas o de rúbricas v1 no traen el campo y no
          se muestra nada acá, igual que hoy (peso-por-subcriterio D8). */}
      {(criterio.subcriterios_evaluados?.length ?? 0) > 0 && (
        <div className="border-t border-border/50 pt-3 mt-1 space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            Desglose por subcriterio
          </p>
          {(criterio.subcriterios_evaluados || []).map((sub) => (
            <div
              key={sub.id}
              className="rounded-md bg-background/60 border border-border/50 p-2.5 text-xs space-y-1"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-foreground">{sub.id}</span>
                <span className="text-muted-foreground">
                  {sub.puntaje_obtenido} / {sub.puntaje_maximo} — {sub.estado}
                </span>
              </div>
              {sub.feedback && (
                <p className="text-muted-foreground">{sub.feedback}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
