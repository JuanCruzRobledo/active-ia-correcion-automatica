/**
 * Modo MANUAL del formulario de rúbricas
 * Con estructura jerárquica completa (criterios → subcriterios → evidencias)
 */

import { useState } from 'react';
import { useFieldArray } from 'react-hook-form';
import type { Control, UseFormRegister, FieldErrors, UseFormWatch, FieldValues } from 'react-hook-form';
import { Plus, Trash2, GripVertical, ChevronDown, ChevronUp } from 'lucide-react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { DndContext, closestCenter, PointerSensor, KeyboardSensor, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import type { DragEndEvent } from '@dnd-kit/core';

import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { cn } from '@/shared/utils/cn';

interface Props {
  control: Control<FieldValues>;
  register: UseFormRegister<FieldValues>;
  errors: FieldErrors<FieldValues>;
  watch: UseFormWatch<FieldValues>;
}

interface CriterioItemProps {
  id: string;
  index: number;
  control: Control<FieldValues>;
  register: UseFormRegister<FieldValues>;
  errors: FieldErrors<FieldValues>;
  remove: (index: number) => void;
  watch: UseFormWatch<FieldValues>;
}

function SortableCriterioItem({
  id,
  index,
  control,
  register,
  errors,
  remove,
  watch,
}: CriterioItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const [isExpanded, setIsExpanded] = useState(true);

  const { fields: subcriteriosFields, append: appendSubcriterio, remove: removeSubcriterio } =
    useFieldArray({
      control,
      name: `criterios_jerarquicos.${index}.subcriterios`,
    });

  const criterioErrors = errors?.criterios_jerarquicos?.[index];

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="bg-card border border-border rounded-lg mb-3"
    >
      {/* Header */}
      <div className="flex items-center gap-2 p-3 bg-muted/30 border-b border-border">
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground"
        >
          <GripVertical className="h-5 w-5" />
        </button>

        <span className="font-medium text-foreground">
          Criterio {watch(`criterios_jerarquicos.${index}.id`) || `C${index + 1}`}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            Peso: {watch(`criterios_jerarquicos.${index}.peso`) || 0}%
          </span>
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-muted-foreground hover:text-foreground"
          >
            {isExpanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
          </button>
          <button
            type="button"
            onClick={() => remove(index)}
            className="text-destructive hover:text-destructive/80"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="ID (ej: C1)"
              {...register(`criterios_jerarquicos.${index}.id`)}
              error={criterioErrors?.id?.message}
              placeholder="C1"
            />
            <Input
              label="Peso (%)"
              type="number"
              {...register(`criterios_jerarquicos.${index}.peso`, { valueAsNumber: true })}
              error={criterioErrors?.peso?.message}
              placeholder="30"
              min={1}
              max={100}
            />
          </div>

          <Input
            label="Nombre"
            {...register(`criterios_jerarquicos.${index}.nombre`)}
            error={criterioErrors?.nombre?.message}
            placeholder="Funcionalidad del código"
          />

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Descripción
            </label>
            <textarea
              {...register(`criterios_jerarquicos.${index}.descripcion`)}
              className={cn(
                'w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none',
                criterioErrors?.descripcion ? 'border-destructive' : 'border-input'
              )}
              rows={2}
              placeholder="Qué evalúa este criterio..."
            />
            {criterioErrors?.descripcion && (
              <p className="text-xs text-destructive mt-1">
                {criterioErrors.descripcion.message}
              </p>
            )}
          </div>

          {/* Subcriterios */}
          <div className="border-t border-border pt-4 mt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium text-foreground">Subcriterios</h4>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  appendSubcriterio({
                    id: `${watch(`criterios_jerarquicos.${index}.id`)}.${subcriteriosFields.length + 1}`,
                    descripcion: '',
                    evidencias: [],
                  })
                }
              >
                <Plus className="h-4 w-4 mr-1" />
                Agregar
              </Button>
            </div>

            {subcriteriosFields.map((subcriterio, subIdx) => (
              <div
                key={subcriterio.id}
                className="bg-muted/20 border border-border rounded-lg p-3 mb-2"
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 space-y-3">
                    <Input
                      label="ID (ej: C1.1)"
                      {...register(`criterios_jerarquicos.${index}.subcriterios.${subIdx}.id`)}
                      error={criterioErrors?.subcriterios?.[subIdx]?.id?.message}
                      placeholder={`${watch(`criterios_jerarquicos.${index}.id`)}.${subIdx + 1}`}
                    />

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-1.5">
                        Descripción
                      </label>
                      <textarea
                        {...register(`criterios_jerarquicos.${index}.subcriterios.${subIdx}.descripcion`)}
                        className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                        rows={2}
                        placeholder="Qué se debe verificar..."
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-1.5">
                        Evidencias (una por línea)
                      </label>
                      <textarea
                        {...register(`criterios_jerarquicos.${index}.subcriterios.${subIdx}.evidencias`, {
                          setValueAs: (v) => typeof v === 'string' ? v.split('\n').filter(Boolean) : v
                        })}
                        className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
                        rows={3}
                        placeholder="Evidencia 1&#10;Evidencia 2&#10;Evidencia 3"
                      />
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => removeSubcriterio(subIdx)}
                    className="text-destructive hover:text-destructive/80 mt-6"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}

            {subcriteriosFields.length === 0 && (
              <p className="text-sm text-muted-foreground italic text-center py-4">
                No hay subcriterios. Agrega al menos uno.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function RubricaManualMode({ control, register, errors, watch }: Props) {
  const {
    fields: criteriosFields,
    append: appendCriterio,
    remove: removeCriterio,
    move: moveCriterio,
  } = useFieldArray({
    control,
    name: 'criterios_jerarquicos',
  });

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = criteriosFields.findIndex((f) => f.id === active.id);
      const newIndex = criteriosFields.findIndex((f) => f.id === over.id);
      moveCriterio(oldIndex, newIndex);
    }
  };

  const criteriosJerarquicos = watch('criterios_jerarquicos') as Array<{ peso?: number }> | undefined;
  const sumaPesos = criteriosJerarquicos?.reduce(
    (sum: number, c) => sum + (c.peso || 0),
    0
  ) || 0;

  const pesoValido = sumaPesos === 100;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">Criterios de Evaluación</h3>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Total:</span>
          <span
            className={cn(
              'text-lg font-bold',
              pesoValido ? 'text-success' : 'text-destructive'
            )}
          >
            {sumaPesos}%
          </span>
          {!pesoValido && (
            <span className="text-sm text-muted-foreground">
              (debe ser 100)
            </span>
          )}
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={criteriosFields.map((f) => f.id)}
          strategy={verticalListSortingStrategy}
        >
          {criteriosFields.map((field, index) => (
            <SortableCriterioItem
              key={field.id}
              id={field.id}
              index={index}
              control={control}
              register={register}
              errors={errors}
              remove={removeCriterio}
              watch={watch}
            />
          ))}
        </SortableContext>
      </DndContext>

      {criteriosFields.length === 0 && (
        <p className="text-sm text-muted-foreground italic text-center py-8 border-2 border-dashed border-border rounded-lg">
          No hay criterios. Agrega al menos uno para comenzar.
        </p>
      )}

      <Button
        type="button"
        variant="outline"
        onClick={() =>
          appendCriterio({
            id: `C${criteriosFields.length + 1}`,
            nombre: '',
            descripcion: '',
            peso: 0,
            instrucciones_puntuacion: '',
            subcriterios: [],
          })
        }
        className="w-full"
      >
        <Plus className="h-4 w-4 mr-2" />
        Agregar Criterio
      </Button>
    </div>
  );
}
