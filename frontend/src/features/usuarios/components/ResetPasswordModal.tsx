// features/usuarios/components/ResetPasswordModal.tsx
/**
 * Modal for confirming password reset
 * Displays the new temporary password after reset
 */

import { useState } from 'react';
import { Modal, Button, Input } from '@/shared/components/ui';
import { useResetPassword } from '../hooks';

export interface ResetPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
  usuarioId: number;
  usuarioNombre: string;
}

export const ResetPasswordModal = ({
  isOpen,
  onClose,
  usuarioId,
  usuarioNombre,
}: ResetPasswordModalProps) => {
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const resetMutation = useResetPassword();

  const handleReset = async () => {
    try {
      const response = await resetMutation.mutateAsync(usuarioId);
      setTempPassword(response.password_temporal);
    } catch (error) {
      console.error('Error resetting password:', error);
    }
  };

  const handleCopyPassword = () => {
    if (!tempPassword) return;
    navigator.clipboard.writeText(tempPassword).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleClose = () => {
    setTempPassword(null);
    setCopied(false);
    onClose();
  };

  // Show password after reset
  if (tempPassword) {
    return (
      <Modal isOpen={isOpen} onClose={handleClose} title="Contraseña reseteada">
        <div className="space-y-4">
          <div className="bg-warning/10 border border-warning/30 rounded-lg p-4">
            <p className="text-sm text-foreground mb-2">
              ⚠️ <strong>Importante:</strong> Guarda esta contraseña temporal. No se volverá a mostrar.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Nueva contraseña temporal para {usuarioNombre}
            </label>
            <div className="flex gap-2">
              <Input value={tempPassword} readOnly className="font-mono" />
              <Button
                variant={copied ? 'success' : 'secondary'}
                onClick={handleCopyPassword}
              >
                {copied ? '✅ ¡Copiado!' : '📋 Copiar'}
              </Button>
            </div>
          </div>

          <div className="bg-info/10 border border-info/30 rounded-lg p-4">
            <p className="text-sm text-foreground">
              El usuario deberá cambiar esta contraseña en su próximo inicio de sesión.
            </p>
          </div>

          <div className="flex justify-end">
            <Button onClick={handleClose}>Entendido</Button>
          </div>
        </div>
      </Modal>
    );
  }

  // Confirmation before reset
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Resetear contraseña">
      <div className="space-y-4">
        <p className="text-foreground">
          ¿Estás seguro de que deseas resetear la contraseña de{' '}
          <strong>{usuarioNombre}</strong>?
        </p>

        <div className="bg-muted border border-border rounded-lg p-4">
          <p className="text-sm text-muted-foreground">
            Se generará una nueva contraseña temporal que deberás comunicar al usuario.
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={resetMutation.isPending}
          >
            Cancelar
          </Button>
          <Button
            onClick={handleReset}
            disabled={resetMutation.isPending}
            isLoading={resetMutation.isPending}
          >
            Resetear contraseña
          </Button>
        </div>
      </div>
    </Modal>
  );
};
