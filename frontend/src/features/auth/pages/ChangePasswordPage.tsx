/**
 * ChangePasswordPage
 *
 * Standalone page for mandatory password change on first login.
 * Mirrors the layout of LoginPage for visual consistency.
 *
 * Guard logic:
 * - Redirects to /login if not authenticated
 * - Redirects to /dashboard if primer_login is already false
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-AUTH-02
 */

import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChangePassword } from '../hooks/useChangePassword';
import { getUser, isAuthenticated } from '../services/auth-service';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';

export const ChangePasswordPage = () => {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const changePasswordMutation = useChangePassword();

  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login', { replace: true });
      return;
    }

    const user = getUser();
    if (user && !user.primer_login) {
      navigate('/dashboard', { replace: true });
    }
  }, [navigate]);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!currentPassword) {
      newErrors.currentPassword = 'La contraseña actual es requerida';
    }

    if (!newPassword) {
      newErrors.newPassword = 'La nueva contraseña es requerida';
    } else if (newPassword.length < 8) {
      newErrors.newPassword = 'La contraseña debe tener al menos 8 caracteres';
    } else if (newPassword === currentPassword) {
      newErrors.newPassword = 'La nueva contraseña debe ser diferente a la actual';
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = 'Debes confirmar la nueva contraseña';
    } else if (confirmPassword !== newPassword) {
      newErrors.confirmPassword = 'Las contraseñas no coinciden';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!validate()) return;

    changePasswordMutation.mutate({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background pt-safe pb-safe pl-safe pr-safe px-4 py-8 overflow-y-auto scroll-momentum">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <img
              src="/active-ia-logo.svg"
              alt="Active-IA Logo"
              className="h-20 w-20"
            />
          </div>
          <h1 className="text-3xl font-bold text-foreground">Active-IA</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Cambio de contraseña obligatorio
          </p>
        </div>

        {/* Form Card: edge-to-edge en mobile, card centrada en sm: */}
        <div className="bg-card rounded-none sm:rounded-lg shadow-sm border border-border p-6 sm:p-8">
          <p className="text-sm text-muted-foreground mb-6">
            Por seguridad, debes cambiar tu contraseña provisional antes de
            continuar usando el sistema.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
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
              helperText="Mínimo 8 caracteres · diferente a la actual · al menos un número"
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

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={changePasswordMutation.isPending}
              isLoading={changePasswordMutation.isPending}
            >
              {changePasswordMutation.isPending
                ? 'Cambiando...'
                : 'Cambiar Contraseña'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};
