// features/comisiones/components/ComisionForm.tsx
/**
 * Form modal for creating and editing comisiones
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-COM-01
 */

import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal, Button, Input, Select, type SelectOption } from '@/shared/components/ui';
import { useCreateComision, useUpdateComision } from '../hooks';
import { useMaterias } from '@/features/materias/hooks';
import type { ComisionDetail } from '../types';

// Validation schema
const comisionSchema = z.object({
  materia_id: z
    .number({ message: 'Selecciona una materia' })
    .positive('Selecciona una materia'),
  nombre: z
    .string()
    .min(1, 'El nombre es requerido')
    .max(50, 'El nombre no puede exceder 50 caracteres'),
  anio: z
    .number({ message: 'El año es requerido' })
    .int('El año debe ser un número entero')
    .min(2020, 'El año debe ser mayor o igual a 2020')
    .max(2100, 'El año debe ser menor o igual a 2100'),
});

type ComisionFormData = z.infer<typeof comisionSchema>;

export interface ComisionFormProps {
  isOpen: boolean;
  onClose: () => void;
  comision?: ComisionDetail; // If provided, edit mode
}

export const ComisionForm = ({ isOpen, onClose, comision }: ComisionFormProps) => {
  const isEditMode = !!comision;
  const currentYear = new Date().getFullYear();

  const createMutation = useCreateComision();
  const updateMutation = useUpdateComision();

  // Fetch materias for selector (only active ones)
  const { data: materiasData, isLoading: isLoadingMaterias } = useMaterias({
    activa: true,
    per_page: 100, // Get all active materias
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setValue,
  } = useForm<ComisionFormData>({
    resolver: zodResolver(comisionSchema),
    defaultValues: {
      materia_id: 0,
      nombre: '',
      anio: currentYear,
    },
  });

  // Load comision data when editing
  useEffect(() => {
    if (comision) {
      setValue('materia_id', comision.materia_id);
      setValue('nombre', comision.nombre);
      setValue('anio', comision.anio);
    } else {
      reset({
        materia_id: 0,
        nombre: '',
        anio: currentYear,
      });
    }
  }, [comision, setValue, reset, currentYear]);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      reset({
        materia_id: 0,
        nombre: '',
        anio: currentYear,
      });
    }
  }, [isOpen, reset, currentYear]);

  const onSubmit = async (data: ComisionFormData) => {
    try {
      if (isEditMode) {
        // Update existing comision (only name can be changed)
        await updateMutation.mutateAsync({
          id: comision.id,
          data: {
            nombre: data.nombre,
          },
        });
      } else {
        // Create new comision
        await createMutation.mutateAsync(data);
      }
      onClose();
    } catch (error) {
      console.error('Error saving comision:', error);
    }
  };

  // Build materia options for select
  const materiaOptions: SelectOption[] = materiasData?.items
    ? [
        { value: '', label: 'Selecciona una materia' },
        ...materiasData.items.map((materia) => ({
          value: materia.id.toString(),
          label: `${materia.codigo} - ${materia.nombre}`,
        })),
      ]
    : [{ value: '', label: 'Selecciona una materia' }];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditMode ? 'Editar Comisión' : 'Crear Comisión'}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Select
          label="Materia"
          options={materiaOptions}
          error={errors.materia_id?.message}
          disabled={isEditMode || isLoadingMaterias} // Cannot change materia when editing
          helperText={isEditMode ? 'La materia no puede modificarse' : undefined}
          {...register('materia_id', {
            setValueAs: (v) => (v === '' ? 0 : parseInt(v, 10)),
          })}
        />

        <Input
          label="Nombre"
          placeholder="Comisión A"
          error={errors.nombre?.message}
          helperText="Nombre identificador de la comisión (ej: Comisión A, Comisión Noche)"
          {...register('nombre')}
        />

        <Input
          label="Año Académico"
          type="number"
          placeholder={currentYear.toString()}
          error={errors.anio?.message}
          disabled={isEditMode} // Cannot change year when editing
          helperText={isEditMode ? 'El año no puede modificarse' : `Año académico de la comisión (actual: ${currentYear})`}
          {...register('anio', {
            setValueAs: (v) => (v === '' ? currentYear : parseInt(v, 10)),
          })}
        />

        {!isEditMode && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-800">
              💡 Después de crear la comisión, podrás asignarle tutores desde la vista de comisiones.
            </p>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={isSubmitting || isLoadingMaterias}
            isLoading={isSubmitting}
          >
            {isEditMode ? 'Guardar cambios' : 'Crear comisión'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
