import { useState } from 'react';
import { Button, Input, Modal } from '@/shared/components/ui';
import { useCreateCohorte, useUpdateCohorte } from '../hooks/useCohortes';
import type { Cohorte } from '../types';

interface CohorteFormModalProps {
  onClose: () => void;
  cohorte?: Cohorte | null;
}

/**
 * Modal para crear/editar una cohorte. El código solo se define al crear
 * (es la clave de la cohorte); al editar se ajusta nombre/estado.
 *
 * Se monta solo mientras está abierto (ver CohortesPage), así el estado inicial
 * se toma directo de las props — sin useEffect de sincronización.
 */
export const CohorteFormModal = ({ onClose, cohorte }: CohorteFormModalProps) => {
  const isEdit = !!cohorte;
  const [codigo, setCodigo] = useState(cohorte?.codigo ?? '');
  const [nombre, setNombre] = useState(cohorte?.nombre ?? '');

  const createMutation = useCreateCohorte();
  const updateMutation = useUpdateCohorte();
  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleSubmit = async () => {
    if (isEdit && cohorte) {
      await updateMutation.mutateAsync({ id: cohorte.id, data: { nombre: nombre || null } });
    } else {
      if (!codigo.trim()) return;
      await createMutation.mutateAsync({ codigo: codigo.trim(), nombre: nombre || null });
    }
    onClose();
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={isEdit ? `Editar cohorte ${cohorte?.codigo}` : 'Nueva cohorte'}
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
          <Button onClick={handleSubmit} isLoading={isPending} className="w-full sm:w-auto">
            {isEdit ? 'Guardar' : 'Crear'}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        {!isEdit && (
          <Input
            label="Código"
            placeholder="Ej: M26, A25"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.toUpperCase())}
            maxLength={10}
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
          />
        )}
        <Input
          label="Nombre (opcional)"
          placeholder="Ej: Marzo 2026"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          maxLength={50}
        />
      </div>
    </Modal>
  );
};
