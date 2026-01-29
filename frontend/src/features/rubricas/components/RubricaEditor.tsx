import { useEffect, useState } from 'react';
import { useForm, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Plus, Trash2 } from 'lucide-react';

import { Modal } from '@/shared/components/ui/Modal';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Select } from '@/shared/components/ui/Select';
import { Spinner } from '@/shared/components/ui/Spinner';

import { useCreateRubrica, useUpdateRubrica } from '../hooks/useRubricas';
import type { Rubrica, TipoRubrica } from '../types';

// ========== SCHEMAS ==========

const criterioSchema = z.object({
  id: z.string(),
  nombre: z.string().min(1, 'Nombre requerido').max(100),
  descripcion: z.string().min(10, 'Mínimo 10 caracteres').max(500),
  puntaje_maximo: z.number().min(1, 'Mínimo 1').max(100, 'Máximo 100'),
});

const rubricaFormSchema = z.object({
  materia_id: z.number().min(1, 'Materia requerida'),
  tipo: z.enum(['TP', 'PARCIAL_1', 'PARCIAL_2', 'RECUPERATORIO_1', 'RECUPERATORIO_2', 'FINAL', 'GLOBAL']),
  nombre: z.string().min(1, 'Nombre requerido').max(200),
  numero: z.number().min(1).max(999),
  anio: z.number().min(2020).max(2100),
  criterios: z
    .array(criterioSchema)
    .min(1, 'Debe haber al menos un criterio')
    .max(20, 'Máximo 20 criterios'),
}).refine(
  (data) => {
    const suma = data.criterios.reduce((acc, c) => acc + c.puntaje_maximo, 0);
    return suma === 100;
  },
  {
    message: 'La suma de puntajes debe ser exactamente 100',
    path: ['criterios'],
  }
);

type RubricaFormData = z.infer<typeof rubricaFormSchema>;

// ========== SORTABLE CRITERIO ITEM ==========

interface CriterioItemProps {
  id: string;
  index: number;
  nombre: string;
  descripcion: string;
  puntaje_maximo: number;
  onUpdate: (index: number, field: string, value: string | number) => void;
  onRemove: (index: number) => void;
  errors?: {
    nombre?: string;
    descripcion?: string;
    puntaje_maximo?: string;
  };
}

function CriterioItem({
  id,
  index,
  nombre,
  descripcion,
  puntaje_maximo,
  onUpdate,
  onRemove,
  errors,
}: CriterioItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex gap-3 p-4 bg-card border border-border rounded-lg"
    >
      {/* Drag Handle */}
      <button
        type="button"
        className="flex-shrink-0 mt-2 text-muted-foreground hover:text-foreground cursor-grab active:cursor-grabbing"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-5 w-5" />
      </button>

      {/* Fields */}
      <div className="flex-1 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Nombre */}
          <div className="md:col-span-2">
            <Input
              label="Nombre del criterio"
              value={nombre}
              onChange={(e) => onUpdate(index, 'nombre', e.target.value)}
              error={errors?.nombre}
              placeholder="ej: Funcionalidad correcta"
            />
          </div>

          {/* Puntaje */}
          <div>
            <Input
              label="Puntaje"
              type="number"
              min={1}
              max={100}
              value={puntaje_maximo}
              onChange={(e) =>
                onUpdate(index, 'puntaje_maximo', parseInt(e.target.value) || 0)
              }
              error={errors?.puntaje_maximo}
              placeholder="40"
            />
          </div>
        </div>

        {/* Descripción */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Descripción
          </label>
          <textarea
            value={descripcion}
            onChange={(e) => onUpdate(index, 'descripcion', e.target.value)}
            className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            rows={2}
            placeholder="¿Qué se evalúa en este criterio?"
          />
          {errors?.descripcion && (
            <p className="mt-1 text-sm text-destructive">{errors.descripcion}</p>
          )}
        </div>
      </div>

      {/* Remove Button */}
      <button
        type="button"
        onClick={() => onRemove(index)}
        className="flex-shrink-0 mt-2 text-muted-foreground hover:text-destructive"
      >
        <Trash2 className="h-5 w-5" />
      </button>
    </div>
  );
}

// ========== MAIN COMPONENT ==========

interface RubricaEditorProps {
  isOpen: boolean;
  onClose: () => void;
  materiaId?: number;
  rubrica?: Rubrica; // Para modo edición
}

const TIPO_LABELS: Record<TipoRubrica, string> = {
  TP: 'Trabajo Práctico',
  PARCIAL_1: 'Parcial 1',
  PARCIAL_2: 'Parcial 2',
  RECUPERATORIO_1: 'Recuperatorio 1',
  RECUPERATORIO_2: 'Recuperatorio 2',
  FINAL: 'Final',
  GLOBAL: 'Global',
};

export function RubricaEditor({
  isOpen,
  onClose,
  materiaId,
  rubrica,
}: RubricaEditorProps) {
  const isEditing = !!rubrica;
  const createMutation = useCreateRubrica();
  const updateMutation = useUpdateRubrica();

  const [sumaPuntajes, setSumaPuntajes] = useState(0);

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
  } = useForm<RubricaFormData>({
    resolver: zodResolver(rubricaFormSchema),
    defaultValues: rubrica
      ? {
          materia_id: rubrica.materia_id,
          tipo: rubrica.tipo,
          nombre: rubrica.nombre,
          numero: rubrica.numero,
          anio: rubrica.anio,
          criterios: rubrica.criterios_json.criterios.map((c) => ({
            id: c.id,
            nombre: c.nombre,
            descripcion: c.descripcion,
            puntaje_maximo: c.puntaje_maximo,
          })),
        }
      : {
          materia_id: materiaId || 0,
          tipo: 'TP',
          nombre: '',
          numero: 1,
          anio: new Date().getFullYear(),
          criterios: [
            {
              id: crypto.randomUUID(),
              nombre: '',
              descripcion: '',
              puntaje_maximo: 100,
            },
          ],
        },
  });

  const { fields, append, remove, move } = useFieldArray({
    control,
    name: 'criterios',
  });

  const criterios = watch('criterios');

  // Calcular suma de puntajes
  useEffect(() => {
    const suma = criterios.reduce((acc, c) => acc + (c.puntaje_maximo || 0), 0);
    setSumaPuntajes(suma);
  }, [criterios]);

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = fields.findIndex((field) => field.id === active.id);
      const newIndex = fields.findIndex((field) => field.id === over.id);
      move(oldIndex, newIndex);
    }
  };

  const handleAddCriterio = () => {
    append({
      id: crypto.randomUUID(),
      nombre: '',
      descripcion: '',
      puntaje_maximo: 0,
    });
  };

  const handleUpdateCriterio = (
    index: number,
    field: string,
    value: string | number
  ) => {
    const currentCriterios = [...criterios];
    currentCriterios[index] = {
      ...currentCriterios[index],
      [field]: value,
    };
    // React Hook Form manejará la actualización
  };

  const onSubmit = async (data: RubricaFormData) => {
    try {
      const criterios_json = {
        puntaje_maximo: 100,
        criterios: data.criterios.map((c) => ({
          id: c.id,
          nombre: c.nombre,
          descripcion: c.descripcion,
          puntaje_maximo: c.puntaje_maximo,
        })),
      };

      if (isEditing) {
        await updateMutation.mutateAsync({
          id: rubrica.id,
          data: {
            nombre: data.nombre,
            criterios_json,
          },
        });
      } else {
        await createMutation.mutateAsync({
          materia_id: data.materia_id,
          tipo: data.tipo,
          nombre: data.nombre,
          numero: data.numero,
          anio: data.anio,
          criterios_json,
        });
      }

      reset();
      onClose();
    } catch (error) {
      console.error('Error guardando rúbrica:', error);
    }
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const isLoading = createMutation.isPending || updateMutation.isPending;
  const puntajeFaltante = 100 - sumaPuntajes;

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isEditing ? 'Editar Rúbrica' : 'Crear Rúbrica'}
      size="xl"
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Información General */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Información General</h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Tipo */}
            <Select
              label="Tipo"
              {...register('tipo')}
              error={errors.tipo?.message}
              disabled={isEditing}
            >
              <option value="">Seleccionar tipo</option>
              {Object.entries(TIPO_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>

            {/* Número */}
            <Input
              label="Número"
              type="number"
              min={1}
              max={999}
              {...register('numero', { valueAsNumber: true })}
              error={errors.numero?.message}
              disabled={isEditing}
            />

            {/* Año */}
            <Input
              label="Año"
              type="number"
              min={2020}
              max={2100}
              {...register('anio', { valueAsNumber: true })}
              error={errors.anio?.message}
              disabled={isEditing}
            />
          </div>

          {/* Nombre */}
          <Input
            label="Nombre"
            {...register('nombre')}
            error={errors.nombre?.message}
            placeholder="ej: TP1 - Listas en Python"
          />
        </div>

        {/* Criterios de Evaluación */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Criterios de Evaluación</h3>

            {/* Indicador de Puntaje */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Total:</span>
              <span
                className={`text-lg font-bold ${
                  sumaPuntajes === 100
                    ? 'text-success'
                    : sumaPuntajes > 100
                    ? 'text-destructive'
                    : 'text-warning'
                }`}
              >
                {sumaPuntajes}/100
              </span>
              {puntajeFaltante !== 0 && (
                <span className="text-sm text-muted-foreground">
                  ({puntajeFaltante > 0 ? `faltan ${puntajeFaltante}` : `sobran ${Math.abs(puntajeFaltante)}`})
                </span>
              )}
            </div>
          </div>

          {errors.criterios && typeof errors.criterios.message === 'string' && (
            <p className="text-sm text-destructive">{errors.criterios.message}</p>
          )}

          {/* Lista de Criterios con Drag and Drop */}
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={fields.map((f) => f.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-3">
                {fields.map((field, index) => (
                  <CriterioItem
                    key={field.id}
                    id={field.id}
                    index={index}
                    nombre={criterios[index]?.nombre || ''}
                    descripcion={criterios[index]?.descripcion || ''}
                    puntaje_maximo={criterios[index]?.puntaje_maximo || 0}
                    onUpdate={handleUpdateCriterio}
                    onRemove={remove}
                    errors={
                      errors.criterios?.[index] as {
                        nombre?: string;
                        descripcion?: string;
                        puntaje_maximo?: string;
                      }
                    }
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>

          {/* Botón Agregar Criterio */}
          <Button
            type="button"
            variant="outline"
            onClick={handleAddCriterio}
            disabled={fields.length >= 20}
            className="w-full"
          >
            <Plus className="h-4 w-4 mr-2" />
            Agregar Criterio
          </Button>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 pt-4 border-t border-border">
          <Button type="button" variant="outline" onClick={handleClose}>
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={isLoading || sumaPuntajes !== 100}
            className="min-w-[120px]"
          >
            {isLoading ? (
              <Spinner size="sm" />
            ) : isEditing ? (
              'Guardar Cambios'
            ) : (
              'Crear Rúbrica'
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
