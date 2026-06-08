// features/usuarios/components/UsuarioForm.tsx
/**
 * Form modal for creating and editing users
 * 
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-USER-01
 */

import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Modal, Button, Input, Select, type SelectOption } from '@/shared/components/ui';
import { useCreateUsuario, useUpdateUsuario } from '../hooks';
import type { Usuario } from '../types';

// Validation schema
const usuarioSchema = z.object({
  username: z
    .string()
    .min(3, 'El username debe tener al menos 3 caracteres')
    .max(50, 'El username no puede exceder 50 caracteres')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Solo letras, números, guiones y guiones bajos'),
  nombre: z
    .string()
    .min(2, 'El nombre debe tener al menos 2 caracteres')
    .max(100, 'El nombre no puede exceder 100 caracteres'),
  rol: z.enum(['ADMIN', 'COORDINADOR', 'TUTOR', 'GESTOR'], {
    message: 'Selecciona un rol válido',
  }),
  email: z
    .union([z.string().email('Email inválido').max(150), z.literal('')])
    .optional(),
});

type UsuarioFormData = z.infer<typeof usuarioSchema>;

export interface UsuarioFormProps {
  isOpen: boolean;
  onClose: () => void;
  usuario?: Usuario; // If provided, edit mode
}

export const UsuarioForm = ({ isOpen, onClose, usuario }: UsuarioFormProps) => {
  const isEditMode = !!usuario;
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyPassword = () => {
    if (!tempPassword) return;
    navigator.clipboard.writeText(tempPassword).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const createMutation = useCreateUsuario();
  const updateMutation = useUpdateUsuario();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setValue,
  } = useForm<UsuarioFormData>({
    resolver: zodResolver(usuarioSchema),
    defaultValues: {
      username: '',
      nombre: '',
      rol: 'TUTOR',
      email: '',
    },
  });

  // Load usuario data when editing
  useEffect(() => {
    if (usuario) {
      setValue('username', usuario.username);
      setValue('nombre', usuario.nombre);
      setValue('rol', usuario.rol);
      setValue('email', usuario.email ?? '');
    } else {
      reset();
    }
  }, [usuario, setValue, reset]);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      reset();
      setTempPassword(null);
      setShowPasswordModal(false);
    }
  }, [isOpen, reset]);

  const onSubmit = async (data: UsuarioFormData) => {
    try {
      const email = data.email?.trim() || null;
      if (isEditMode) {
        // Update existing user
        await updateMutation.mutateAsync({
          id: usuario.id,
          data: {
            nombre: data.nombre,
            rol: data.rol,
            email,
          },
        });
        onClose();
      } else {
        // Create new user
        const response = await createMutation.mutateAsync({
          username: data.username,
          nombre: data.nombre,
          rol: data.rol,
          email,
        });
        setTempPassword(response.password_temporal);
        setShowPasswordModal(true);
      }
    } catch (error) {
      console.error('Error saving usuario:', error);
    }
  };

  const handlePasswordModalClose = () => {
    setShowPasswordModal(false);
    setTempPassword(null);
    onClose();
  };

  const rolOptions: SelectOption[] = [
    { value: 'ADMIN', label: 'Administrador' },
    { value: 'COORDINADOR', label: 'Coordinador' },
    { value: 'TUTOR', label: 'Tutor' },
    { value: 'GESTOR', label: 'Gestor' },
  ];

  // Password display modal
  if (showPasswordModal && tempPassword) {
    return (
      <Modal
        isOpen={showPasswordModal}
        onClose={handlePasswordModalClose}
        title="Usuario creado exitosamente"
      >
        <div className="space-y-4">
          <div className="bg-warning/10 border border-warning/30 rounded-lg p-4">
            <p className="text-sm text-foreground mb-2">
              ⚠️ <strong>Importante:</strong> Guarda esta contraseña temporal. No se volverá a mostrar.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Contraseña temporal
            </label>
            <div className="flex gap-2">
              <Input
                value={tempPassword}
                readOnly
                className="font-mono"
              />
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
              El usuario deberá cambiar esta contraseña en su primer inicio de sesión.
            </p>
          </div>

          <div className="flex justify-end">
            <Button onClick={handlePasswordModalClose}>
              Entendido
            </Button>
          </div>
        </div>
      </Modal>
    );
  }

  // Main form modal
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditMode ? 'Editar Usuario' : 'Crear Usuario'}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Username"
          placeholder="jperez"
          error={errors.username?.message}
          disabled={isEditMode} // Username cannot be changed
          {...register('username')}
        />

        <Input
          label="Nombre completo"
          placeholder="Juan Pérez"
          error={errors.nombre?.message}
          {...register('nombre')}
        />

        <Select
          label="Rol"
          options={rolOptions}
          error={errors.rol?.message}
          {...register('rol')}
        />

        <Input
          label="Email (opcional)"
          type="email"
          placeholder="jperez@active-ia.com"
          error={errors.email?.message}
          {...register('email')}
        />
        <p className="-mt-2 text-xs text-muted-foreground">
          Necesario para que un tutor reciba el PDF semanal de actividades faltantes.
        </p>

        {!isEditMode && (
          <div className="bg-muted border border-border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">
              💡 Se generará automáticamente una contraseña temporal que se mostrará al crear el usuario.
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
            disabled={isSubmitting}
            isLoading={isSubmitting}
          >
            {isEditMode ? 'Guardar cambios' : 'Crear usuario'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
