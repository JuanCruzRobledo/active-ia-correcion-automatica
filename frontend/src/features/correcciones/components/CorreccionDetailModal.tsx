// features/correcciones/components/CorreccionDetailModal.tsx
/**
 * Modal para ver y editar una corrección.
 *
 * Permite modificar:
 * - Nota final
 * - Puntaje por criterio
 * - Estado de criterio (OK, WARNING, ERROR)
 * - Feedback de cada criterio
 * - Fortalezas (agregar/eliminar)
 * - Recomendaciones (agregar/eliminar)
 * - Comentario general
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md - Modal de Detalle/Edición
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md - HU-EDIT-01
 */

import { useState, useEffect } from 'react';
import { X, Plus, Calculator } from 'lucide-react';
import { Modal } from '../../../shared/components/ui/Modal';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Select } from '../../../shared/components/ui/Select';
import { Badge } from '../../../shared/components/ui/Badge';
import { useUpdateCorreccion } from '../hooks/useCorrecciones';
import type { Correccion, CriterioEvaluado, EstadoCriterio } from '../types';

interface CorreccionDetailModalProps {
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
 * Modal para editar corrección completa.
 *
 * Estructura:
 * - Header: Alumno y trabajo
 * - Nota final con botón recalcular
 * - Criterios de evaluación (editables)
 * - Fortalezas (lista editable)
 * - Recomendaciones (lista editable)
 * - Comentario general
 * - Footer: Cancelar / Guardar
 */
export default function CorreccionDetailModal({
  correccion,
  alumno,
  trabajoNombre,
  isOpen,
  onClose,
}: CorreccionDetailModalProps) {
  // Estado local del formulario
  const [nota, setNota] = useState(correccion.nota);
  const [criterios, setCriterios] = useState<CriterioEvaluado[]>(
    correccion.criterios
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

  // Estado de inputs temporales para agregar items
  const [nuevaFortaleza, setNuevaFortaleza] = useState('');
  const [nuevaRecomendacion, setNuevaRecomendacion] = useState('');

  // Mutation hook
  const updateMutation = useUpdateCorreccion();

  // Resetear estado local cuando cambia la corrección
  useEffect(() => {
    setNota(correccion.nota);
    setCriterios(correccion.criterios);
    setFortalezas(correccion.fortalezas);
    setRecomendaciones(correccion.recomendaciones);
    setComentarioGeneral(correccion.comentario_general);
  }, [correccion]);

  /**
   * Recalcula la nota sumando los puntajes de todos los criterios.
   */
  const handleRecalcularNota = () => {
    const notaCalculada = criterios.reduce(
      (sum, c) => sum + c.puntaje_obtenido,
      0
    );
    setNota(notaCalculada);
  };

  /**
   * Actualiza un criterio específico.
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
   * Agrega una nueva fortaleza a la lista.
   */
  const handleAgregarFortaleza = () => {
    if (nuevaFortaleza.trim()) {
      setFortalezas([...fortalezas, nuevaFortaleza.trim()]);
      setNuevaFortaleza('');
    }
  };

  /**
   * Elimina una fortaleza por índice.
   */
  const handleEliminarFortaleza = (index: number) => {
    setFortalezas(fortalezas.filter((_, i) => i !== index));
  };

  /**
   * Agrega una nueva recomendación a la lista.
   */
  const handleAgregarRecomendacion = () => {
    if (nuevaRecomendacion.trim()) {
      setRecomendaciones([...recomendaciones, nuevaRecomendacion.trim()]);
      setNuevaRecomendacion('');
    }
  };

  /**
   * Elimina una recomendación por índice.
   */
  const handleEliminarRecomendacion = (index: number) => {
    setRecomendaciones(recomendaciones.filter((_, i) => i !== index));
  };

  /**
   * Guarda los cambios enviando al backend.
   */
  const handleGuardar = () => {
    updateMutation.mutate(
      {
        correccionId: correccion.id,
        data: {
          nota,
          criterios,
          fortalezas,
          recomendaciones,
          comentario_general: comentarioGeneral,
        },
      },
      {
        onSuccess: () => {
          onClose();
        },
      }
    );
  };

  /**
   * Cancela cambios y cierra modal.
   */
  const handleCancelar = () => {
    // Resetear a valores originales
    setNota(correccion.nota);
    setCriterios(correccion.criterios);
    setFortalezas(correccion.fortalezas);
    setRecomendaciones(correccion.recomendaciones);
    setComentarioGeneral(correccion.comentario_general);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleCancelar} size="2xl">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-border pb-4 mb-6">
        <div>
          <h2 className="text-xl font-semibold text-foreground">
            Corrección: {alumno}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {trabajoNombre}
          </p>
        </div>
        <button
          onClick={handleCancelar}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Cerrar modal"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Content - Scrollable */}
      <div className="space-y-6 max-h-[calc(100vh-16rem)] overflow-y-auto pr-2">
        {/* Nota Final */}
        <section className="bg-muted/50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-foreground">NOTA FINAL</h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRecalcularNota}
              className="gap-2"
            >
              <Calculator className="h-4 w-4" />
              Recalcular
            </Button>
          </div>
          <div className="bg-background rounded-md p-6 text-center">
            <input
              type="number"
              min="0"
              max="100"
              step="0.5"
              value={nota}
              onChange={(e) => setNota(Number(e.target.value))}
              className="text-4xl font-bold text-center w-32 bg-transparent border-b-2 border-border focus:border-accent focus:outline-none"
            />
            <span className="text-2xl text-muted-foreground ml-2">/ 100</span>
          </div>
        </section>

        {/* Criterios de Evaluación */}
        <section>
          <h3 className="text-sm font-medium text-foreground mb-4">
            CRITERIOS DE EVALUACIÓN
          </h3>
          <div className="space-y-4">
            {criterios.map((criterio, index) => (
              <CriterioEditor
                key={criterio.id}
                criterio={criterio}
                onChange={(field, value) =>
                  handleCriterioChange(index, field, value)
                }
              />
            ))}
          </div>
        </section>

        {/* Fortalezas */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-foreground">FORTALEZAS</h3>
            <div className="flex gap-2">
              <Input
                type="text"
                value={nuevaFortaleza}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNuevaFortaleza(e.target.value)}
                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAgregarFortaleza();
                  }
                }}
                placeholder="Nueva fortaleza..."
                className="w-64"
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
          </div>
          <ul className="space-y-2">
            {fortalezas.map((fortaleza, index) => (
              <li
                key={index}
                className="flex items-start justify-between bg-muted/50 rounded-md p-3"
              >
                <span className="flex-1 text-sm">• {fortaleza}</span>
                <button
                  onClick={() => handleEliminarFortaleza(index)}
                  className="text-muted-foreground hover:text-destructive transition-colors ml-2"
                  aria-label="Eliminar fortaleza"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
            {fortalezas.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No hay fortalezas registradas. Agrega una arriba.
              </p>
            )}
          </ul>
        </section>

        {/* Recomendaciones */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-foreground">
              RECOMENDACIONES
            </h3>
            <div className="flex gap-2">
              <Input
                type="text"
                value={nuevaRecomendacion}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNuevaRecomendacion(e.target.value)}
                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAgregarRecomendacion();
                  }
                }}
                placeholder="Nueva recomendación..."
                className="w-64"
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
          </div>
          <ol className="space-y-2">
            {recomendaciones.map((recomendacion, index) => (
              <li
                key={index}
                className="flex items-start justify-between bg-muted/50 rounded-md p-3"
              >
                <span className="flex-1 text-sm">
                  {index + 1}. {recomendacion}
                </span>
                <button
                  onClick={() => handleEliminarRecomendacion(index)}
                  className="text-muted-foreground hover:text-destructive transition-colors ml-2"
                  aria-label="Eliminar recomendación"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
            {recomendaciones.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No hay recomendaciones registradas. Agrega una arriba.
              </p>
            )}
          </ol>
        </section>

        {/* Comentario General */}
        <section>
          <h3 className="text-sm font-medium text-foreground mb-3">
            COMENTARIO GENERAL
          </h3>
          <textarea
            value={comentarioGeneral}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setComentarioGeneral(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder="Comentario general para el alumno..."
          />
        </section>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-6">
        <Button variant="ghost" onClick={handleCancelar}>
          Cancelar
        </Button>
        <Button
          variant="primary"
          onClick={handleGuardar}
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? 'Guardando...' : 'Guardar Cambios'}
        </Button>
      </div>
    </Modal>
  );
}

/**
 * Editor de un criterio individual.
 */
interface CriterioEditorProps {
  criterio: CriterioEvaluado;
  onChange: (field: keyof CriterioEvaluado, value: string | number) => void;
}

function CriterioEditor({ criterio, onChange }: CriterioEditorProps) {
  const estadoOptions: { value: EstadoCriterio; label: string }[] = [
    { value: 'OK', label: '✓ OK' },
    { value: 'WARNING', label: '⚠ Warning' },
    { value: 'ERROR', label: '✗ Error' },
  ];

  // Generar opciones de puntaje (0 hasta puntaje_maximo)
  const puntajeOptions = Array.from(
    { length: criterio.puntaje_maximo + 1 },
    (_, i) => ({
      value: i.toString(),
      label: i.toString(),
    })
  );

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      {/* Header del criterio */}
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-foreground">{criterio.nombre}</h4>
        <Badge
          variant={
            criterio.estado === 'OK'
              ? 'success'
              : criterio.estado === 'WARNING'
              ? 'warning'
              : 'destructive'
          }
        >
          {criterio.estado}
        </Badge>
      </div>

      {/* Puntaje y Estado */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Puntaje
          </label>
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
        </div>

        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Estado
          </label>
          <Select
            value={criterio.estado}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
              onChange('estado', e.target.value as EstadoCriterio)
            }
            options={estadoOptions}
          />
        </div>
      </div>

      {/* Feedback */}
      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5">
          Feedback
        </label>
        <textarea
          value={criterio.feedback}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => onChange('feedback', e.target.value)}
          rows={3}
          className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          placeholder="Feedback específico para este criterio..."
        />
      </div>
    </div>
  );
}
