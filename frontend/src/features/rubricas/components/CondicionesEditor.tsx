import { useFieldArray, type Control, type UseFormRegister, type FieldErrors } from 'react-hook-form';
import { Plus, Trash2, XCircle } from 'lucide-react';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { cn } from '@/shared/utils/cn';

interface CondicionesEditorProps {
  control: Control<any>;
  register: UseFormRegister<any>;
  errors: FieldErrors<any>;
}

export function CondicionesEditor({
  control,
  register,
  errors,
}: CondicionesEditorProps) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: 'condiciones_desaprobacion',
  });

  return (
    <div className="space-y-4">
      {/* Info */}
      <div className="flex gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-md">
        <XCircle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
        <div className="text-sm">
          <p className="font-medium mb-1 text-foreground">Condiciones de desaprobación automática</p>
          <p className="text-muted-foreground">
            Define condiciones que establecen una nota final específica automáticamente, independientemente de otros criterios.
            <span className="block mt-1 text-xs">Ej: "Plagio detectado" → Nota: 0, "Falta más del 50% de funcionalidad" → Nota: 30</span>
          </p>
        </div>
      </div>

      {/* Lista de condiciones */}
      {fields.length > 0 ? (
        <div className="space-y-3">
          {fields.map((field, index) => {
            const fieldErrors = (errors?.condiciones_desaprobacion as any)?.[index];

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
                        {...register(`condiciones_desaprobacion.${index}.id`)}
                        error={fieldErrors?.id?.message as string}
                        placeholder="CD1"
                      />
                      <div className="col-span-2">
                        <Input
                          label="Nota Final"
                          type="number"
                          min={0}
                          max={100}
                          {...register(`condiciones_desaprobacion.${index}.nota_final`, {
                            valueAsNumber: true,
                          })}
                          error={fieldErrors?.nota_final?.message as string}
                          placeholder="0"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-foreground mb-1.5">
                        Condición
                      </label>
                      <textarea
                        {...register(`condiciones_desaprobacion.${index}.condicion`)}
                        className={cn(
                          'w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none',
                          fieldErrors?.condicion ? 'border-destructive' : 'border-input'
                        )}
                        rows={2}
                        placeholder="Ej: Plagio detectado o código copiado de otra fuente"
                      />
                      {fieldErrors?.condicion && (
                        <p className="text-xs text-destructive mt-1">
                          {fieldErrors.condicion.message as string}
                        </p>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => remove(index)}
                    className="text-destructive hover:text-destructive/80 mt-6"
                    title="Eliminar condición"
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
          <XCircle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">
            No hay condiciones de desaprobación definidas
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Las condiciones son opcionales
          </p>
        </div>
      )}

      {/* Botón agregar */}
      <Button
        type="button"
        variant="outline"
        onClick={() =>
          append({
            id: `CD${fields.length + 1}`,
            condicion: '',
            nota_final: 0,
          })
        }
        className="w-full"
      >
        <Plus className="h-4 w-4 mr-2" />
        Agregar Condición
      </Button>
    </div>
  );
}
