import { useState } from 'react';
import { Button, Checkbox, Input, Modal } from '@/shared/components/ui';
import { useCreateTutorNexo, useUpdateTutorNexo } from '../hooks/useTutoresNexo';
import type { TutorNexo } from '../types';

interface TutorNexoFormModalProps {
  onClose: () => void;
  tutorNexo?: TutorNexo | null;
}

/**
 * Modal para crear/editar un tutor nexo. Se monta solo mientras está abierto,
 * así el estado inicial se toma directo de las props (sin useEffect de sync).
 */
export const TutorNexoFormModal = ({ onClose, tutorNexo }: TutorNexoFormModalProps) => {
  const isEdit = !!tutorNexo;
  const [nombre, setNombre] = useState(tutorNexo?.nombre ?? '');
  const [email, setEmail] = useState(tutorNexo?.email ?? '');
  const [regional, setRegional] = useState(tutorNexo?.regional ?? '');
  const [activo, setActivo] = useState(tutorNexo?.activo ?? true);

  const createMutation = useCreateTutorNexo();
  const updateMutation = useUpdateTutorNexo();
  const isPending = createMutation.isPending || updateMutation.isPending;

  const completo = nombre.trim() && email.trim() && regional.trim();

  const handleSubmit = async () => {
    if (!completo) return;
    if (isEdit && tutorNexo) {
      await updateMutation.mutateAsync({
        id: tutorNexo.id,
        data: { nombre: nombre.trim(), email: email.trim(), regional: regional.trim(), activo },
      });
    } else {
      await createMutation.mutateAsync({
        nombre: nombre.trim(),
        email: email.trim(),
        regional: regional.trim(),
      });
    }
    onClose();
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={isEdit ? `Editar tutor nexo` : 'Nuevo tutor nexo'}
      size="md"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit} isLoading={isPending} disabled={!completo}>
            {isEdit ? 'Guardar' : 'Crear'}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <Input
          label="Nombre"
          placeholder="Ej: María López"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          maxLength={150}
        />
        <Input
          label="Email"
          type="email"
          inputMode="email"
          autoCapitalize="none"
          autoComplete="email"
          autoCorrect="off"
          spellCheck={false}
          placeholder="nexo.mendoza@active-ia.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          maxLength={150}
        />
        <Input
          label="Regional"
          placeholder="Ej: Mendoza (sin el prefijo R-)"
          value={regional}
          onChange={(e) => setRegional(e.target.value)}
          maxLength={120}
        />
        {isEdit && (
          <label className="flex min-h-11 cursor-pointer items-center gap-2 py-2 text-sm text-foreground touch-manipulation">
            <Checkbox checked={activo} onChange={() => setActivo((v) => !v)} />
            Activo (recibe el Excel semanal)
          </label>
        )}
      </div>
    </Modal>
  );
};
