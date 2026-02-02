// features/materias/components/MateriaForm.tsx
/**
 * Form modal for creating and editing materias with coordinator assignment
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-MAT-01, HU-MAT-02
 */

import { useEffect, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal, Button, Input } from '@/shared/components/ui';
import { MultiSelect } from '@/shared/components/ui/MultiSelect';
import { useCreateMateria, useUpdateMateria } from '../hooks';
import { useCoordinadores } from '@/features/usuarios/hooks';
import type { MateriaDetail } from '../types';

// Validation schema
const materiaSchema = z.object({
  codigo: z
    .string()
    .min(2, 'El código debe tener al menos 2 caracteres')
    .max(20, 'El código no puede exceder 20 caracteres')
    .regex(/^[A-Z0-9_-]+$/, 'Solo mayúsculas, números, guiones y guiones bajos'),
  nombre: z
    .string()
    .min(2, 'El nombre debe tener al menos 2 caracteres')
    .max(100, 'El nombre no puede exceder 100 caracteres'),
  descripcion: z
    .string()
    .max(500, 'La descripción no puede exceder 500 caracteres')
    .optional(),
  coordinador_ids: z.array(z.number()).optional(),
});

type MateriaFormData = z.infer<typeof materiaSchema>;

export interface MateriaFormProps {
  isOpen: boolean;
  onClose: () => void;
  materia?: MateriaDetail; // If provided, edit mode (with coordinadores)
}

export const MateriaForm = ({ isOpen, onClose, materia }: MateriaFormProps) => {
  const isEditMode = !!materia;

  const createMutation = useCreateMateria();
  const updateMutation = useUpdateMateria();
  const { data: coordinadores = [], isLoading: loadingCoordinadores } = useCoordinadores();

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
    reset,
    setValue,
  } = useForm<MateriaFormData>({
    resolver: zodResolver(materiaSchema),
    defaultValues: {
      codigo: '',
      nombre: '',
      descripcion: '',
      coordinador_ids: [],
    },
  });

  // Load materia data when editing
  useEffect(() => {
    if (materia) {
      setValue('codigo', materia.codigo);
      setValue('nombre', materia.nombre);
      setValue('descripcion', materia.descripcion || '');
      setValue('coordinador_ids', materia.coordinadores?.map((c) => c.id) || []);
    } else {
      reset();
    }
  }, [materia, setValue, reset]);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      reset();
    }
  }, [isOpen, reset]);

  const onSubmit = async (data: MateriaFormData) => {
    try {
      if (isEditMode) {
        // Update existing materia
        await updateMutation.mutateAsync({
          id: materia.id,
          data: {
            nombre: data.nombre,
            descripcion: data.descripcion || undefined,
            coordinador_ids: data.coordinador_ids,
          },
        });
      } else {
        // Create new materia
        await createMutation.mutateAsync({
          codigo: data.codigo,
          nombre: data.nombre,
          descripcion: data.descripcion,
          coordinador_ids: data.coordinador_ids,
        });
      }
      onClose();
    } catch (error) {
      console.error('Error saving materia:', error);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditMode ? 'Editar Materia' : 'Crear Materia'}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Código"
          placeholder="PROG1"
          error={errors.codigo?.message}
          disabled={isEditMode} // Código cannot be changed
          helperText="Identificador único (ej: PROG1). Solo mayúsculas."
          {...register('codigo')}
        />

        <Input
          label="Nombre"
          placeholder="Programación 1"
          error={errors.nombre?.message}
          {...register('nombre')}
        />

        <Input
          label="Descripción (Opcional)"
          placeholder="Conceptos básicos de programación..."
          error={errors.descripcion?.message}
          {...register('descripcion')}
        // Using Input as text field for now, ideally Textarea
        />

        <Controller
          name="coordinador_ids"
          control={control}
          render={({ field }) => (
            <MultiSelect
              label="Coordinadores (Opcional)"
              placeholder="Selecciona coordinadores"
              tooltip="Usuarios con rol COORDINADOR que pueden gestionar esta materia"
              options={coordinadores.map((c) => ({
                value: c.id,
                label: c.nombre,
              }))}
              value={field.value || []}
              onChange={field.onChange}
              loading={loadingCoordinadores}
              error={errors.coordinador_ids?.message}
            />
          )}
        />

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
            disabled={isSubmitting}
            isLoading={isSubmitting}
          >
            {isEditMode ? 'Guardar cambios' : 'Crear materia'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
