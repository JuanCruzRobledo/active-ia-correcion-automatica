/**
 * ChangePasswordModal Component
 *
 * Modal for forced password change on first login.
 * Cannot be closed until password is successfully changed.
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-AUTH-02
 */

import { useState } from 'react';
import type { FormEvent } from 'react';
import { useChangePassword } from '../hooks/useChangePassword';
import { Modal } from '@/shared/components/ui/Modal';
import { Input } from '@/shared/components/ui/Input';
import { Button } from '@/shared/components/ui/Button';

interface ChangePasswordModalProps {
  isOpen: boolean;
}

export const ChangePasswordModal = ({ isOpen }: ChangePasswordModalProps) => {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const changePasswordMutation = useChangePassword();

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // Validar contraseña actual
    if (!currentPassword) {
      newErrors.currentPassword = 'La contraseña actual es requerida';
    }

    // Validar nueva contraseña
    if (!newPassword) {
      newErrors.newPassword = 'La nueva contraseña es requerida';
    } else if (newPassword.length < 8) {
      newErrors.newPassword = 'La contraseña debe tener al menos 8 caracteres';
    } else if (newPassword === currentPassword) {
      newErrors.newPassword = 'La nueva contraseña debe ser diferente a la actual';
    }

    // Validar confirmación
    if (!confirmPassword) {
      newErrors.confirmPassword = 'Debes confirmar la nueva contraseña';
    } else if (confirmPassword !== newPassword) {
      newErrors.confirmPassword = 'Las contraseñas no coinciden';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    changePasswordMutation.mutate({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => {}} // No-op: modal cannot be closed manually
      title="Cambio de Contraseña Obligatorio"
      size="md"
      disableBackdropClose={true}
      disableEscapeClose={true}
    >
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Por seguridad, debes cambiar tu contraseña provisional antes de continuar.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Contraseña Actual"
            type="password"
            value={currentPassword}
            onChange={(e) => {
              setCurrentPassword(e.target.value);
              setErrors((prev) => ({ ...prev, currentPassword: '' }));
            }}
            placeholder="Ingresa tu contraseña actual"
            disabled={changePasswordMutation.isPending}
            error={errors.currentPassword}
            required
            autoComplete="current-password"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />

          <Input
            label="Nueva Contraseña"
            type="password"
            value={newPassword}
            onChange={(e) => {
              setNewPassword(e.target.value);
              setErrors((prev) => ({ ...prev, newPassword: '' }));
            }}
            placeholder="Mínimo 8 caracteres"
            disabled={changePasswordMutation.isPending}
            error={errors.newPassword}
            helperText="La contraseña debe tener al menos 8 caracteres y ser diferente a la actual"
            required
            autoComplete="new-password"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />

          <Input
            label="Confirmar Nueva Contraseña"
            type="password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              setErrors((prev) => ({ ...prev, confirmPassword: '' }));
            }}
            placeholder="Repite la nueva contraseña"
            disabled={changePasswordMutation.isPending}
            error={errors.confirmPassword}
            required
            autoComplete="new-password"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />

          {changePasswordMutation.isError && (
            <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
              {changePasswordMutation.error instanceof Error
                ? changePasswordMutation.error.message
                : 'Error al cambiar la contraseña. Intenta nuevamente.'}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="submit"
              variant="primary"
              className="w-full sm:w-auto"
              disabled={changePasswordMutation.isPending}
              isLoading={changePasswordMutation.isPending}
            >
              {changePasswordMutation.isPending ? 'Cambiando...' : 'Cambiar Contraseña'}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
};
