import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Checkbox, Input, Modal } from '@/shared/components/ui';
import { useCreateUniversidad, useUpdateUniversidad } from '../hooks';
import type { Universidad, UniversidadListItem } from '../types';

/** El form sólo lee id/nombre/moodle_host/activa — sirve tanto para el item
 * reducido de la tabla (UniversidadListItem) como para el recurso completo. */
type UniversidadFormTarget = Pick<
  Universidad | UniversidadListItem,
  'id' | 'nombre' | 'moodle_host' | 'activa'
>;

const universidadSchema = z.object({
  nombre: z.string().min(1, 'El nombre es requerido').max(200),
  moodle_host: z.union([z.literal(''), z.string().url('Ingresá una URL válida')]),
  activa: z.boolean(),
});
type UniversidadFormValues = z.infer<typeof universidadSchema>;

interface UniversidadFormProps {
  onClose: () => void;
  universidad?: UniversidadFormTarget | null;
}

/**
 * Modal de alta/edición de universidad (ABM, sólo superadmin).
 *
 * Se monta sólo mientras está abierto (mismo patrón que CohorteFormModal): el
 * estado inicial se toma directo de las props, sin useEffect de sincronización.
 */
export const UniversidadForm = ({ onClose, universidad }: UniversidadFormProps) => {
  const isEdit = !!universidad;
  const createMutation = useCreateUniversidad();
  const updateMutation = useUpdateUniversidad();
  const isPending = createMutation.isPending || updateMutation.isPending;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UniversidadFormValues>({
    resolver: zodResolver(universidadSchema),
    defaultValues: {
      nombre: universidad?.nombre ?? '',
      moodle_host: universidad?.moodle_host ?? '',
      activa: universidad?.activa ?? true,
    },
  });

  const onSubmit = async (data: UniversidadFormValues) => {
    const payload = { nombre: data.nombre, moodle_host: data.moodle_host || null };
    if (isEdit && universidad) {
      await updateMutation.mutateAsync({
        id: universidad.id,
        payload: { ...payload, activa: data.activa },
      });
    } else {
      await createMutation.mutateAsync(payload);
    }
    onClose();
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={isEdit ? `Editar ${universidad?.nombre}` : 'Nueva universidad'}
      size="md"
      footer={
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={isPending}
            className="w-full sm:w-auto"
          >
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit(onSubmit)}
            isLoading={isPending}
            className="w-full sm:w-auto"
          >
            {isEdit ? 'Guardar' : 'Crear'}
          </Button>
        </div>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Nombre"
          placeholder="Ej: TUPaD"
          error={errors.nombre?.message}
          {...register('nombre')}
        />
        <Input
          label="Campus (Host Moodle, opcional)"
          type="url"
          placeholder="https://moodle.ejemplo.com"
          error={errors.moodle_host?.message}
          {...register('moodle_host')}
        />
        {isEdit && (
          <Checkbox label="Activa" {...register('activa')} />
        )}
      </form>
    </Modal>
  );
};
