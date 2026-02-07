import { useFieldArray, type Control, type UseFormRegister, type FieldErrors } from 'react-hook-form';
import { Plus, Trash2, AlertTriangle } from 'lucide-react';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { cn } from '@/shared/utils/cn';

interface PenalizacionesEditorProps {
  control: Control<any>;
  register: UseFormRegister<any>;
  errors: FieldErrors<any>;
}

export function PenalizacionesEditor({
  control,
  register,
  errors,
}: PenalizacionesEditorProps) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: 'penalizaciones',
  });

  return (
    <div className="space-y-4">
      {/* Info */}
      <div className="flex gap-2 p-3 bg-warning/10 border border-warning/20 rounded-md">
        <AlertTriangle className="h-4 w-4 text-warning mt-0.5 flex-shrink-0" />
        <div className="text-sm">
          <p className="font-medium mb-1 text-foreground">Penalizaciones opcionales</p>
          <p className="text-muted-foreground">
            Define descuentos porcentuales que se aplican automáticamente cuando se detectan incumplimientos específicos.
            <span className="block mt-1 text-xs">Ej: "Repositorio privado" → -100%, "Sin README" → -20%</span>
          </p>
        </div>
      </div>

      {/* Lista de penalizaciones */}
      {fields.length > 0 ? (
        <div className="space-y-3">
          {fields.map((field, index) => {
            const fieldErrors = (errors?.penalizaciones as any)?.[index];

            return (
              <div
                key={field.id}
                className="p-3 bg-card border border-border rounded-lg"
              >
                <div className="flex items-start gap-2">
                  <div className="flex-1 space-y-3">
                    <div className="grid grid-cols-3 gap-3">
                      <Input
                        label="ID"
                        {...register(`penalizaciones.${index}.id`)}
                        error={fieldErrors?.id?.message as string}
                        placeholder="P1"
                      />
                      <div className="col-span-2">
                        <Input
                          label="Descuento (%)"
                          type="number"
                          min={0}
                          max={100}
                          {...register(`penalizaciones.${index}.descuento_porcentaje`, {
                            valueAsNumber: true,
                          })}
                          error={fieldErrors?.descuento_porcentaje?.message as string}
                          placeholder="50"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-1.5">
                        Descripción
                      </label>
                      <textarea
                        {...register(`penalizaciones.${index}.descripcion`)}
                        className={cn(
                          'w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none',
                          fieldErrors?.descripcion ? 'border-destructive' : 'border-input'
                        )}
                        rows={2}
                        placeholder="Ej: Repositorio privado o inaccesible"
                      />
                      {fieldErrors?.descripcion && (
                        <p className="text-xs text-destructive mt-1">
                          {fieldErrors.descripcion.message as string}
                        </p>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => remove(index)}
                    className="text-destructive hover:text-destructive/80 mt-6"
                    title="Eliminar penalización"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8 border-2 border-dashed border-border rounded-md">
          <AlertTriangle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">
            No hay penalizaciones definidas
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Las penalizaciones son opcionales
          </p>
        </div>
      )}

      {/* Botón agregar */}
      <Button
        type="button"
        variant="outline"
        onClick={() =>
          append({
            id: `P${fields.length + 1}`,
            descripcion: '',
            descuento_porcentaje: 0,
          })
        }
        className="w-full"
      >
        <Plus className="h-4 w-4 mr-2" />
        Agregar Penalización
      </Button>
    </div>
  );
}
