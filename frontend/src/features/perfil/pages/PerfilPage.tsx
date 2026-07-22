import { useState, useEffect, useId } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Info, Shield, User as UserIcon, Globe, Mail, Sparkles } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useProfile, useUpdateApiKey, useChangePassword, useUpdateKeyPaga, useUpdateEmail, useUpdateCorrectionProvider } from '../hooks/usePerfil';
import type { CorrectionProvider } from '../types';
import { updateMoodleCredentials } from '../services/perfil-service';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Modal } from '../../../shared/components/ui/Modal';
import { Badge } from '../../../shared/components/ui/Badge';
import { HelpButton, LoadingState } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { formatFechaHoraArg } from '@/shared/utils/fecha';

const moodleSchema = z.object({
  moodle_host: z.string().url('Ingresá una URL válida').min(1),
  moodle_username: z.string().min(1, 'El usuario es requerido'),
  moodle_password: z.string().min(1, 'La contraseña es requerida'),
});
type MoodleForm = z.infer<typeof moodleSchema>;

// Metadata por proveedor de corrección (label, ayuda para obtener la key).
const PROVIDER_META: Record<
  CorrectionProvider,
  { nombre: string; descripcion: string; helpUrl: string; helpLabel: string }
> = {
  gemini: {
    nombre: 'Gemini Studio',
    descripcion: 'Tu API Key personal de Google Gemini (AI Studio).',
    helpUrl: 'https://aistudio.google.com/api-keys',
    helpLabel: '¿Cómo obtener una API Key de Gemini? →',
  },
  openrouter: {
    nombre: 'OpenRouter (beta)',
    descripcion:
      'Tu API Key de OpenRouter. Corrige con el modelo google/gemini-3.5-flash.',
    helpUrl: 'https://openrouter.ai/keys',
    helpLabel: '¿Cómo obtener una API Key de OpenRouter? →',
  },
};

export const PerfilPage = () => {
  const { data: profile, isLoading } = useProfile();
  const updateApiKeyMutation = useUpdateApiKey();
  const updateCorrectionProviderMutation = useUpdateCorrectionProvider();
  const updateKeyPagaMutation = useUpdateKeyPaga();
  const updateEmailMutation = useUpdateEmail();
  const changePasswordMutation = useChangePassword();
  const queryClient = useQueryClient();

  // Email de notificaciones (editable inline).
  const [emailInput, setEmailInput] = useState('');
  const [emailError, setEmailError] = useState('');

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
      setEmailInput(profile.email ?? '');
    }
  }, [profile]);

  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  const handleEmailSubmit = () => {
    setEmailError('');
    const limpio = emailInput.trim();
    if (limpio && !EMAIL_RE.test(limpio)) {
      setEmailError('Ingresá un email válido (o dejalo vacío para quitarlo).');
      return;
    }
    updateEmailMutation.mutate(limpio || null);
  };

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
  // UI-012: ids estables para asociar cada label con su Input (htmlFor/id).
  const currentPasswordId = useId();
  const newPasswordId = useId();
  const confirmPasswordId = useId();

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

  // Proveedor de corrección activo + estado de SU key (cada uno guarda la suya).
  const activeProvider: CorrectionProvider = profile.correction_provider ?? 'gemini';
  const isOpenRouter = activeProvider === 'openrouter';
  const providerMeta = PROVIDER_META[activeProvider];
  const keyValid = isOpenRouter
    ? profile.openrouter_api_key_valid
    : profile.gemini_api_key_valid;
  const keyLast4 = isOpenRouter
    ? profile.openrouter_api_key_last_4
    : profile.gemini_api_key_last_4;

  const handleApiKeySubmit = () => {
    setApiKeyError('');

    updateApiKeyMutation.mutate(
      { apiKey, provider: activeProvider },
      {
        onSuccess: () => {
          setShowApiKeyModal(false);
          setApiKey('');
        },
        onError: () => {
          setApiKeyError('Error al validar la API Key. Verifica que sea correcta.');
        },
      }
    );
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

  const formatDate = (dateString: string | null) =>
    dateString ? formatFechaHoraArg(dateString) : 'Nunca';

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
    <div className="space-y-4 sm:space-y-6">
      <div>
        <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground sm:text-3xl">Mi Perfil</h1><HelpButton title="Ayuda — Mi Perfil" content={helpContent.perfil} /></div>
        <p className="text-sm text-muted-foreground">
          Configuración de cuenta y API Key
        </p>
      </div>

      {/* Información del Usuario */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
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

      {/* Email de notificaciones */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <div className="flex items-center gap-3 mb-6">
          <Mail className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold text-foreground">Email de notificaciones</h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 rounded-md bg-muted/50">
            <Info className="h-5 w-5 text-info mt-0.5 flex-shrink-0" />
            <p className="text-sm text-muted-foreground">
              Es la dirección donde vas a recibir las notificaciones (por ejemplo, el PDF con
              las actividades faltantes de tus comisiones). No afecta tu acceso: seguís
              entrando con tu usuario. Dejalo vacío si no querés recibir notificaciones.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Correo electrónico
            </label>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
              <div className="flex-1">
                <Input
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  placeholder="tucorreo@ejemplo.com"
                  value={emailInput}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmailInput(e.target.value)}
                  className={emailError ? 'border-destructive' : ''}
                />
                {emailError && <p className="text-sm text-destructive mt-1.5">{emailError}</p>}
              </div>
              <Button
                onClick={handleEmailSubmit}
                disabled={updateEmailMutation.isPending || (emailInput.trim() === (profile.email ?? ''))}
                isLoading={updateEmailMutation.isPending}
                className="w-full sm:w-auto"
              >
                Guardar
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Modo de corrección + API Key del proveedor activo */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <div className="flex items-center gap-3 mb-6">
          <Sparkles className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold text-foreground">
            Corrección con IA
          </h2>
        </div>

        <div className="space-y-4">
          {/* Slider de modo de corrección */}
          <div>
            <label className="text-sm font-medium text-foreground">
              Modo de corrección
            </label>
            <p className="mb-2 mt-0.5 text-xs text-muted-foreground">
              Elegí qué proveedor usás para corregir. Cada modo guarda su propia API Key.
            </p>
            <div
              role="tablist"
              aria-label="Modo de corrección"
              className="grid grid-cols-2 gap-1 rounded-lg border border-border bg-muted/40 p-1"
            >
              {(['gemini', 'openrouter'] as CorrectionProvider[]).map((p) => {
                const selected = activeProvider === p;
                return (
                  <button
                    key={p}
                    role="tab"
                    aria-selected={selected}
                    onClick={() => {
                      if (!selected) updateCorrectionProviderMutation.mutate(p);
                    }}
                    disabled={updateCorrectionProviderMutation.isPending}
                    className={`min-h-[44px] rounded-md px-3 py-2 text-sm font-medium transition-colors touch-manipulation disabled:cursor-not-allowed ${
                      selected
                        ? 'bg-card text-foreground shadow-sm ring-1 ring-border'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {PROVIDER_META[p].nombre}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Info + ayuda del proveedor activo */}
          <div className="flex items-start gap-3 p-4 rounded-md bg-muted/50">
            <Info className="h-5 w-5 text-info mt-0.5 flex-shrink-0" />
            <div className="text-sm text-muted-foreground">
              <p className="mb-2">
                {providerMeta.descripcion} Se almacena de forma segura y encriptada (AES-256).
              </p>
              <a
                href={providerMeta.helpUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                {providerMeta.helpLabel}
              </a>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <label className="text-sm font-medium text-foreground">
                API Key de {providerMeta.nombre}
              </label>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {keyValid ? (
                  <>
                    <Badge variant="success">Configurada</Badge>
                    {keyLast4 && (
                      <span className="text-sm text-muted-foreground break-all">
                        ****{keyLast4}
                      </span>
                    )}
                  </>
                ) : (
                  <Badge variant="warning">No configurada</Badge>
                )}
              </div>
            </div>

            <Button
              variant={keyValid ? 'secondary' : 'primary'}
              onClick={() => setShowApiKeyModal(true)}
              className="w-full sm:w-auto"
            >
              {keyValid ? 'Cambiar' : 'Configurar'}
            </Button>
          </div>

          {/* Toggle: API key paga (solo Gemini Studio — su free tier limita RPM) */}
          {!isOpenRouter && profile.gemini_api_key_valid && (
            <div className="mt-4 flex items-start justify-between gap-3 rounded-md border border-border bg-muted/20 px-4 py-3">
              <div className="min-w-0">
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

          {isOpenRouter && (
            <p className="rounded-md bg-info/10 px-3 py-2 text-xs text-info">
              OpenRouter es pago por créditos: la corrección masiva “Corregir todo”
              queda habilitada automáticamente sin un toggle de facturación.
            </p>
          )}
        </div>
      </div>

      {/* Configuración Moodle */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
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
                inputMode="url"
                autoComplete="url"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
                autoComplete="current-password"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
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
                className="w-full sm:w-auto"
              >
                {moodleMutation.isPending ? 'Guardando...' : 'Guardar credenciales'}
              </Button>
            </div>
          </form>
        </div>
      </div>

      {/* Seguridad */}
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <div className="flex items-center gap-3 mb-6">
          <Shield className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold text-foreground">Seguridad</h2>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <label className="text-sm font-medium text-foreground">
              Contraseña
            </label>
            <p className="text-sm text-muted-foreground mt-1">
              Actualiza tu contraseña regularmente para mantener tu cuenta
              segura
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => setShowPasswordModal(true)}
            className="w-full sm:w-auto"
          >
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
          keyValid
            ? `Cambiar API Key de ${providerMeta.nombre}`
            : `Configurar API Key de ${providerMeta.nombre}`
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
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder="Ingresá tu API Key"
                value={apiKey}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setApiKey(e.target.value)
                }
                className={apiKeyError ? 'border-destructive pr-11' : 'pr-11'}
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                aria-label={showApiKey ? 'Ocultar API Key' : 'Mostrar API Key'}
                className="absolute right-1 top-1/2 inline-flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground touch-manipulation sm:min-h-0 sm:min-w-0 sm:right-3"
              >
                {showApiKey ? (
                  <EyeOff className="h-5 w-5 sm:h-4 sm:w-4" />
                ) : (
                  <Eye className="h-5 w-5 sm:h-4 sm:w-4" />
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

          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
            <Button
              variant="ghost"
              onClick={() => {
                setShowApiKeyModal(false);
                setApiKey('');
                setApiKeyError('');
              }}
              disabled={updateApiKeyMutation.isPending}
              className="w-full sm:w-auto"
            >
              Cancelar
            </Button>
            <Button
              onClick={handleApiKeySubmit}
              disabled={!apiKey || updateApiKeyMutation.isPending}
              isLoading={updateApiKeyMutation.isPending}
              className="w-full sm:w-auto"
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
            <label htmlFor={currentPasswordId} className="block text-sm font-medium text-foreground mb-1.5">
              Contraseña actual
            </label>
            <div className="relative">
              <Input
                id={currentPasswordId}
                type={showCurrentPassword ? 'text' : 'password'}
                autoComplete="current-password"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder="••••••••"
                value={currentPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setCurrentPassword(e.target.value)
                }
                className="pr-11"
              />
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                aria-label={showCurrentPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                className="absolute right-1 top-1/2 inline-flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground touch-manipulation sm:min-h-0 sm:min-w-0 sm:right-3"
              >
                {showCurrentPassword ? (
                  <EyeOff className="h-5 w-5 sm:h-4 sm:w-4" />
                ) : (
                  <Eye className="h-5 w-5 sm:h-4 sm:w-4" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label htmlFor={newPasswordId} className="block text-sm font-medium text-foreground mb-1.5">
              Nueva contraseña
            </label>
            <div className="relative">
              <Input
                id={newPasswordId}
                type={showNewPassword ? 'text' : 'password'}
                autoComplete="new-password"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder="••••••••"
                value={newPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setNewPassword(e.target.value)
                }
                className={passwordError ? 'border-destructive pr-11' : 'pr-11'}
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                aria-label={showNewPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                className="absolute right-1 top-1/2 inline-flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground touch-manipulation sm:min-h-0 sm:min-w-0 sm:right-3"
              >
                {showNewPassword ? (
                  <EyeOff className="h-5 w-5 sm:h-4 sm:w-4" />
                ) : (
                  <Eye className="h-5 w-5 sm:h-4 sm:w-4" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label htmlFor={confirmPasswordId} className="block text-sm font-medium text-foreground mb-1.5">
              Confirmar nueva contraseña
            </label>
            <div className="relative">
              <Input
                id={confirmPasswordId}
                type={showConfirmPassword ? 'text' : 'password'}
                autoComplete="new-password"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setConfirmPassword(e.target.value)
                }
                className={passwordError ? 'border-destructive pr-11' : 'pr-11'}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                className="absolute right-1 top-1/2 inline-flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground touch-manipulation sm:min-h-0 sm:min-w-0 sm:right-3"
              >
                {showConfirmPassword ? (
                  <EyeOff className="h-5 w-5 sm:h-4 sm:w-4" />
                ) : (
                  <Eye className="h-5 w-5 sm:h-4 sm:w-4" />
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

          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
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
              className="w-full sm:w-auto"
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
              className="w-full sm:w-auto"
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
