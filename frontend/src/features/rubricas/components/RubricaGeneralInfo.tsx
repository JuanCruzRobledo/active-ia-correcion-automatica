import type { UseFormRegister, FieldErrors, UseFormWatch, UseFormSetValue } from 'react-hook-form';
import { Input } from '@/shared/components/ui/Input';
import { Select } from '@/shared/components/ui/Select';
import { cn } from '@/shared/utils/cn';
import { TIPO_LABELS } from '../constants/rubrica-constants';
import type { CreationMode } from '../constants/rubrica-constants';

interface Props {
  register: UseFormRegister<any>;
  errors: FieldErrors<any>;
  watch: UseFormWatch<any>;
  setValue: UseFormSetValue<any>;
  materiasData?: { items: Array<{ id: number; codigo: string; nombre: string }> };
  isEditing: boolean;
  creationMode: CreationMode;
}

export function RubricaGeneralInfo({
  register,
  errors,
  watch,
  setValue,
  materiasData,
  isEditing,
  creationMode,
}: Props) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Información General</h3>

      <Select
        label="Materia"
        value={watch('materia_id')?.toString() || ''}
        onChange={(e) =>
          setValue('materia_id', e.target.value ? parseInt(e.target.value) : 0, {
            shouldValidate: true,
          })
        }
        error={errors.materia_id?.message as string}
        disabled={isEditing}
      >
        <option value="">Seleccionar materia</option>
        {(materiasData?.items || []).map((m) => (
          <option key={m.id} value={m.id.toString()}>
            {m.codigo} - {m.nombre}
          </option>
        ))}
      </Select>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Select
          label="Tipo"
          {...register('tipo')}
          error={errors.tipo?.message as string}
          disabled={isEditing}
        >
          <option value="">Seleccionar tipo</option>
          {Object.entries(TIPO_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>

        <Input
          label="Número"
          type="number"
          min={1}
          max={999}
          {...register('numero', { valueAsNumber: true })}
          error={errors.numero?.message as string}
          disabled={isEditing || creationMode === 'pdf'}
        />

        <Input
          label="Año"
          type="number"
          min={2020}
          max={2100}
          {...register('anio', { valueAsNumber: true })}
          error={errors.anio?.message as string}
          disabled={isEditing}
        />
      </div>

      <Input
        label="Título"
        {...register('titulo')}
        error={errors.titulo?.message as string}
        placeholder="ej: TP2 - API REST de Productos"
        disabled={creationMode === 'pdf'}
      />

      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Descripción</label>
        <textarea
          {...register('descripcion')}
          className={cn(
            'w-full px-3 py-2 border rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none',
            errors.descripcion ? 'border-destructive' : 'border-input'
          )}
          rows={3}
          placeholder="Describe qué evalúa esta rúbrica..."
          disabled={creationMode === 'pdf'}
        />
        {errors.descripcion && (
          <p className="text-xs text-destructive mt-1">{errors.descripcion.message as string}</p>
        )}
      </div>

      {creationMode === 'pdf' && (
        <p className="text-xs text-muted-foreground">
          Los campos se generarán automáticamente desde el PDF
        </p>
      )}
    </div>
  );
}
