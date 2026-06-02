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
    },
  });

  // Load usuario data when editing
  useEffect(() => {
    if (usuario) {
      setValue('username', usuario.username);
      setValue('nombre', usuario.nombre);
      setValue('rol', usuario.rol);
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
      if (isEditMode) {
        // Update existing user
        await updateMutation.mutateAsync({
          id: usuario.id,
          data: {
            nombre: data.nombre,
            rol: data.rol,
          },
        });
        onClose();
      } else {
        // Create new user
        const response = await createMutation.mutateAsync(data);
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
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-sm text-yellow-800 mb-2">
              ⚠️ <strong>Importante:</strong> Guarda esta contraseña temporal. No se volverá a mostrar.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
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

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-800">
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

        {!isEditMode && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-600">
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
