// features/comisiones/components/ComisionForm.tsx
/**
 * Form modal for creating and editing comisiones with tutor assignment
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-COM-01, HU-COM-02
 */

import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal, Button, Input, Select, type SelectOption } from '@/shared/components/ui';
import { MultiSelect } from '@/shared/components/ui/MultiSelect';
import { useCreateComision, useUpdateComision } from '../hooks';
import { useMaterias } from '@/features/materias/hooks';
import { useTutores } from '@/features/usuarios/hooks';
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
  tutor_ids: z.array(z.number()).optional(),
  moodle_group_id: z
    .number()
    .int()
    .positive('Debe ser un número positivo')
    .nullable()
    .optional(),
  moodle_group_code: z.string().max(50).nullable().optional(),
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

  const { data: tutores = [], isLoading: loadingTutores } = useTutores();

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
    reset,
    setValue,
  } = useForm<ComisionFormData>({
    resolver: zodResolver(comisionSchema),
    defaultValues: {
      materia_id: 0,
      nombre: '',
      anio: currentYear,
      tutor_ids: [],
      moodle_group_id: null,
      moodle_group_code: null,
    },
  });

  // Load comision data when editing
  useEffect(() => {
    if (comision) {
      setValue('materia_id', comision.materia_id);
      setValue('nombre', comision.nombre);
      setValue('anio', comision.anio);
      setValue('tutor_ids', comision.tutores?.map((t) => t.id) || []);
      setValue('moodle_group_id', comision.moodle_group_id ?? null);
      setValue('moodle_group_code', comision.moodle_group_code ?? null);
    } else {
      reset({
        materia_id: 0,
        nombre: '',
        anio: currentYear,
        tutor_ids: [],
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
        tutor_ids: [],
      });
    }
  }, [isOpen, reset, currentYear]);

  const onSubmit = async (data: ComisionFormData) => {
    try {
      if (isEditMode) {
        // Update existing comision
        await updateMutation.mutateAsync({
          id: comision.id,
          data: {
            nombre: data.nombre,
            tutor_ids: data.tutor_ids,
            moodle_group_id: data.moodle_group_id ?? undefined,
            moodle_group_code: data.moodle_group_code ?? undefined,
          },
        });
      } else {
        // Create new comision
        await createMutation.mutateAsync({
          materia_id: data.materia_id,
          nombre: data.nombre,
          anio: data.anio,
          tutor_ids: data.tutor_ids,
          moodle_group_id: data.moodle_group_id ?? undefined,
          moodle_group_code: data.moodle_group_code ?? undefined,
        });
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

        <Controller
          name="tutor_ids"
          control={control}
          render={({ field }) => (
            <MultiSelect
              label="Tutores (Opcional)"
              placeholder="Selecciona tutores"
              tooltip="Usuarios con rol TUTOR que pueden corregir entregas de esta comisión"
              options={tutores.map((t) => ({
                value: t.id,
                label: t.nombre,
              }))}
              value={field.value || []}
              onChange={field.onChange}
              loading={loadingTutores}
              error={errors.tutor_ids?.message}
            />
          )}
        />

        <div className="space-y-4 rounded-md border border-border bg-muted/30 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Configuración Moodle
          </p>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="ID de Grupo Moodle"
              type="number"
              placeholder="ej: 4165"
              helperText="moodle_group_id"
              error={errors.moodle_group_id?.message}
              {...register('moodle_group_id', {
                setValueAs: (v) => (v === '' || v === null ? null : Number(v)),
              })}
            />
            <Input
              label="Código de Grupo Moodle"
              placeholder="ej: m26"
              helperText="groupsearchvalue"
              error={errors.moodle_group_code?.message}
              {...register('moodle_group_code', {
                setValueAs: (v) => (v === '' ? null : v),
              })}
            />
          </div>
        </div>

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
