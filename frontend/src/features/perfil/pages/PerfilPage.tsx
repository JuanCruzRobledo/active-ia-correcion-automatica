import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Key, Info, Shield, User as UserIcon, Globe } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useProfile, useUpdateApiKey, useChangePassword, useUpdateKeyPaga } from '../hooks/usePerfil';
import { updateMoodleCredentials } from '../services/perfil-service';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Modal } from '../../../shared/components/ui/Modal';
import { Badge } from '../../../shared/components/ui/Badge';
import { HelpButton, LoadingState } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';

const moodleSchema = z.object({
  moodle_host: z.string().url('Ingresá una URL válida').min(1),
  moodle_username: z.string().min(1, 'El usuario es requerido'),
  moodle_password: z.string().min(1, 'La contraseña es requerida'),
});
type MoodleForm = z.infer<typeof moodleSchema>;

export const PerfilPage = () => {
  const { data: profile, isLoading } = useProfile();
  const updateApiKeyMutation = useUpdateApiKey();
  const updateKeyPagaMutation = useUpdateKeyPaga();
  const changePasswordMutation = useChangePassword();
  const queryClient = useQueryClient();

  const moodleForm = useForm<MoodleForm>({
    resolver: zodResolver(moodleSchema),
    defaultValues: { moodle_host: '', moodle_username: '', moodle_password: '' },
  });

  useEffect(() => {
    if (profile) {
      moodleForm.reset({
        moodle_host: profile.moodle_host ?? '',
        moodle_username: profile.moodle_username ?? '',
        moodle_password: '',
      });
    }
  }, [profile]);

  const moodleMutation = useMutation({
    mutationFn: updateMoodleCredentials,
    onSuccess: (data) => {
      toast.success('Credenciales Moodle guardadas');
      moodleForm.reset({
        moodle_host: data.moodle_host,
        moodle_username: data.moodle_username,
        moodle_password: '',
      });
      queryClient.invalidateQueries({ queryKey: ['pendientes-moodle'] });
    },
    onError: () => {
      toast.error('Error al guardar credenciales Moodle');
    },
  });

  // API Key modal state
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKeyError, setApiKeyError] = useState('');

  // Password modal state
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordError, setPasswordError] = useState('');

  if (isLoading) {
    return <LoadingState title="Cargando tu perfil…" />;
  }

  if (!profile) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Error al cargar el perfil</p>
      </div>
    );
  }

  const handleApiKeySubmit = () => {
    setApiKeyError('');

    updateApiKeyMutation.mutate(apiKey, {
      onSuccess: () => {
        setShowApiKeyModal(false);
        setApiKey('');
      },
      onError: () => {
        setApiKeyError('Error al validar la API Key. Verifica que sea correcta.');
      },
    });
  };

  const handlePasswordSubmit = () => {
    setPasswordError('');

    // Validaciones
    if (newPassword.length < 8) {
      setPasswordError('La nueva contraseña debe tener al menos 8 caracteres');
      return;
    }

    if (!/\d/.test(newPassword)) {
      setPasswordError('La nueva contraseña debe contener al menos un número');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('Las contraseñas no coinciden');
      return;
    }

    if (currentPassword === newPassword) {
      setPasswordError('La nueva contraseña debe ser diferente a la actual');
      return;
    }

    changePasswordMutation.mutate(
      {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      },
      {
        onSuccess: () => {
          setShowPasswordModal(false);
          setCurrentPassword('');
          setNewPassword('');
          setConfirmPassword('');
        },
        onError: () => {
          setPasswordError('Error al cambiar la contraseña. Verifica tu contraseña actual.');
        },
      }
    );
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Nunca';
    return new Date(dateString).toLocaleDateString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getRolColor = (rol: string) => {
    switch (rol.toLowerCase()) {
      case 'admin':
        return 'destructive';
      case 'coordinador':
        return 'warning';
      case 'tutor':
        return 'info';
      default:
        return 'default';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2"><h1 className="text-3xl font-bold text-foreground">Mi Perfil</h1><HelpButton title="Ayuda — Mi Perfil" content={helpContent.perfil} /></div>
        <p className="text-sm text-muted-foreground">
          Configuración de cuenta y API Key
        </p>
      </div>

      {/* Información del Usuario */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <UserIcon className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold text-foreground">
            Información Personal
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Nombre completo
            </label>
            <p className="text-base text-foreground mt-1">{profile.nombre}</p>
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Nombre de usuario
            </label>
            <p className="text-base text-foreground mt-1">{profile.username}</p>
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Rol
            </label>
            <div className="mt-1">
              <Badge variant={getRolColor(profile.rol)}>
                {profile.rol.charAt(0).toUpperCase() + profile.rol.slice(1)}
              </Badge>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Estado
            </label>
            <div className="mt-1">
              <Badge variant={profile.activo ? 'success' : 'default'}>
                {profile.activo ? 'Activo' : 'Inactivo'}
              </Badge>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Fecha de creación
            </label>
            <p className="text-base text-foreground mt-1">
              {formatDate(profile.created_at)}
            </p>
          </div>

          <div>
            <label className="text-sm font-medium text-muted-foreground">
              Último acceso
            </label>
            <p className="text-base text-foreground mt-1">
              {formatDate(profile.last_login)}
            </p>
          </div>
        </div>
      </div>

      {/* Configuración de API Key */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <Key className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold text-foreground">
            API Key de Google Gemini
          </h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 rounded-md bg-muted/50">
            <Info className="h-5 w-5 text-info mt-0.5 flex-shrink-0" />
            <div className="text-sm text-muted-foreground">
              <p className="mb-2">
                Tu API Key personal de Google Gemini se usa para las
                correcciones automáticas. Se almacena de forma segura y
                encriptada.
              </p>
              <a
                href="https://aistudio.google.com/api-keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                ¿Cómo obtener una API Key? →
              </a>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium text-foreground">
                Estado de la API Key
              </label>
              <div className="flex items-center gap-2 mt-1">
                {profile.gemini_api_key_valid ? (
                  <>
                    <Badge variant="success">Configurada</Badge>
                    {profile.gemini_api_key_last_4 && (
                      <span className="text-sm text-muted-foreground">
                        ****{profile.gemini_api_key_last_4}
                      </span>
                    )}
                  </>
                ) : (
                  <Badge variant="warning">No configurada</Badge>
                )}
              </div>
            </div>

            <Button
              variant={profile.gemini_api_key_valid ? 'secondary' : 'primary'}
              onClick={() => setShowApiKeyModal(true)}
            >
              {profile.gemini_api_key_valid ? 'Cambiar' : 'Configurar'}
            </Button>
          </div>

          {/* Toggle: API key paga (habilita corrección masiva global) */}
          {profile.gemini_api_key_valid && (
            <div className="mt-4 flex items-start justify-between gap-3 rounded-md border border-border bg-muted/20 px-4 py-3">
              <div>
                <label className="text-sm font-medium text-foreground">
                  API key con facturación habilitada (paga)
                </label>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Activalo solo si habilitaste billing en Google Cloud. Habilita el botón
                  “Corregir todo” (corrección masiva de todas tus entregas).
                </p>
              </div>
              <input
                type="checkbox"
                checked={profile.gemini_api_key_paga}
                onChange={(e) => updateKeyPagaMutation.mutate(e.target.checked)}
                disabled={updateKeyPagaMutation.isPending}
                className="mt-1 h-5 w-5 shrink-0 cursor-pointer"
                aria-label="API key paga"
              />
            </div>
          )}
        </div>
      </div>

      {/* Configuración Moodle */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <Globe className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold text-foreground">Configuración Moodle</h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 rounded-md bg-muted/50">
            <Info className="h-5 w-5 text-info mt-0.5 flex-shrink-0" />
            <p className="text-sm text-muted-foreground">
              Ingresá tus credenciales de Moodle para visualizar las entregas pendientes de
              corrección directamente desde Active-IA. La contraseña se cifra con AES-256.
            </p>
          </div>

          <form
            onSubmit={moodleForm.handleSubmit((data) => moodleMutation.mutate(data))}
            className="space-y-4"
          >
            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                Host Moodle
              </label>
              <Input
                type="url"
                placeholder="https://moodle.ejemplo.com"
                {...moodleForm.register('moodle_host')}
                className={moodleForm.formState.errors.moodle_host ? 'border-destructive' : ''}
              />
              {moodleForm.formState.errors.moodle_host && (
                <p className="text-sm text-destructive mt-1">
                  {moodleForm.formState.errors.moodle_host.message}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                Usuario Moodle
              </label>
              <Input
                type="text"
                placeholder="usuario@moodle"
                {...moodleForm.register('moodle_username')}
                className={moodleForm.formState.errors.moodle_username ? 'border-destructive' : ''}
              />
              {moodleForm.formState.errors.moodle_username && (
                <p className="text-sm text-destructive mt-1">
                  {moodleForm.formState.errors.moodle_username.message}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                Contraseña Moodle
              </label>
              <Input
                type="password"
                placeholder="••••••••"
                {...moodleForm.register('moodle_password')}
                className={moodleForm.formState.errors.moodle_password ? 'border-destructive' : ''}
              />
              {moodleForm.formState.errors.moodle_password && (
                <p className="text-sm text-destructive mt-1">
                  {moodleForm.formState.errors.moodle_password.message}
                </p>
              )}
            </div>

            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={moodleMutation.isPending}
                isLoading={moodleMutation.isPending}
              >
                {moodleMutation.isPending ? 'Guardando...' : 'Guardar credenciales'}
              </Button>
            </div>
          </form>
        </div>
      </div>

      {/* Seguridad */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <Shield className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold text-foreground">Seguridad</h2>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <label className="text-sm font-medium text-foreground">
              Contraseña
            </label>
            <p className="text-sm text-muted-foreground mt-1">
              Actualiza tu contraseña regularmente para mantener tu cuenta
              segura
            </p>
          </div>

          <Button variant="secondary" onClick={() => setShowPasswordModal(true)}>
            Cambiar contraseña
          </Button>
        </div>
      </div>

      {/* Modal de API Key */}
      <Modal
        isOpen={showApiKeyModal}
        onClose={() => {
          setShowApiKeyModal(false);
          setApiKey('');
          setApiKeyError('');
        }}
        title={
          profile.gemini_api_key_valid
            ? 'Cambiar API Key de Gemini'
            : 'Configurar API Key de Gemini'
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              API Key
            </label>
            <div className="relative">
              <Input
                type={showApiKey ? 'text' : 'password'}
                placeholder="Ingresá tu API Key"
                value={apiKey}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setApiKey(e.target.value)
                }
                className={apiKeyError ? 'border-destructive' : ''}
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showApiKey ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            {apiKeyError && (
              <p className="text-sm text-destructive mt-1.5">{apiKeyError}</p>
            )}
          </div>

          <div className="flex items-start gap-2 p-3 rounded-md bg-muted/50">
            <Info className="h-4 w-4 text-info mt-0.5 flex-shrink-0" />
            <p className="text-sm text-muted-foreground">
              La API Key se validará automáticamente antes de guardarla.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => {
                setShowApiKeyModal(false);
                setApiKey('');
                setApiKeyError('');
              }}
              disabled={updateApiKeyMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={handleApiKeySubmit}
              disabled={!apiKey || updateApiKeyMutation.isPending}
              isLoading={updateApiKeyMutation.isPending}
            >
              {updateApiKeyMutation.isPending ? 'Validando...' : 'Guardar'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal de Cambio de Contraseña */}
      <Modal
        isOpen={showPasswordModal}
        onClose={() => {
          setShowPasswordModal(false);
          setCurrentPassword('');
          setNewPassword('');
          setConfirmPassword('');
          setPasswordError('');
        }}
        title="Cambiar contraseña"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Contraseña actual
            </label>
            <div className="relative">
              <Input
                type={showCurrentPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={currentPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setCurrentPassword(e.target.value)
                }
              />
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showCurrentPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Nueva contraseña
            </label>
            <div className="relative">
              <Input
                type={showNewPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={newPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setNewPassword(e.target.value)
                }
                className={passwordError ? 'border-destructive' : ''}
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showNewPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Confirmar nueva contraseña
            </label>
            <div className="relative">
              <Input
                type={showConfirmPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setConfirmPassword(e.target.value)
                }
                className={passwordError ? 'border-destructive' : ''}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showConfirmPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            {passwordError && (
              <p className="text-sm text-destructive mt-1.5">{passwordError}</p>
            )}
          </div>

          <div className="flex items-start gap-2 p-3 rounded-md bg-muted/50">
            <Info className="h-4 w-4 text-info mt-0.5 flex-shrink-0" />
            <p className="text-sm text-muted-foreground">
              La contraseña debe tener al menos 8 caracteres y contener al menos
              un número.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => {
                setShowPasswordModal(false);
                setCurrentPassword('');
                setNewPassword('');
                setConfirmPassword('');
                setPasswordError('');
              }}
              disabled={changePasswordMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={handlePasswordSubmit}
              disabled={
                !currentPassword ||
                !newPassword ||
                !confirmPassword ||
                changePasswordMutation.isPending
              }
              isLoading={changePasswordMutation.isPending}
            >
              {changePasswordMutation.isPending
                ? 'Cambiando...'
                : 'Cambiar contraseña'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
