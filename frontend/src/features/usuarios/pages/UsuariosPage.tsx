// features/usuarios/pages/UsuariosPage.tsx
/**
 * Usuarios management page for Admin role
 * 
 * Displays table of users with filters and CRUD actions
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 3
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { useState, useEffect, useRef } from 'react';
import toast from 'react-hot-toast';
import { Pencil, Key, Trash2, RotateCcw, MoreVertical } from 'lucide-react';
import { useUsuarios, useDeleteUsuario, useRestoreUsuario } from '../hooks';
import { UsuarioForm, ResetPasswordModal } from '../components';
import type { Usuario, UsuarioListItem } from '../types';
import type { RolEnum, UsuariosFilters } from '../types';
import {
  Button,
  Input,
  Select,
  Badge,
  ResponsiveTable,
  LoadingState,
  HelpButton,
  EmptyState,
  Dropdown,
  ConfirmDialog,
  type TableColumn,
  type SelectOption,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { formatDate } from '@/shared/utils';

// Textos del diálogo de confirmación de borrado (extraídos para un único punto
// de edición). El borrado es soft delete → se puede restaurar luego.
const ELIMINAR_DIALOG = {
  title: 'Eliminar usuario',
  message:
    '¿Seguro que querés eliminar a este usuario? Podés restaurarlo luego desde el filtro de eliminados.',
  confirmLabel: 'Eliminar',
} as const;

// Estado del diálogo de confirmación, alineado con el patrón de EntregasPage.
type ConfirmState = {
  title: string;
  message: string;
  confirmLabel: string;
  variant: 'primary' | 'destructive' | 'success';
  onConfirm: () => void | Promise<void>;
};

// Mapeo de rol -> variante/label de Badge, reutilizado en la tabla (desktop)
// y en la tarjeta mobile.
const rolVariants: Record<RolEnum, 'destructive' | 'info' | 'success'> = {
  ADMIN: 'destructive',
  COORDINADOR: 'info',
  TUTOR: 'success',
  GESTOR: 'info',
};

const rolLabels: Record<RolEnum, string> = {
  ADMIN: 'Administrador',
  COORDINADOR: 'Coordinador',
  TUTOR: 'Tutor',
  GESTOR: 'Gestor',
};

export const UsuariosPage = () => {
  const [inputSearch, setInputSearch] = useState('');
  const [filters, setFilters] = useState<UsuariosFilters>({
    rol: 'TODOS',
    activo: 'TODOS',
    search: '',
    page: 1,
    per_page: 20,
  });
  const isFirstRender = useRef(true);

  // Debounce: actualiza el filtro 400ms después de que el usuario deja de escribir
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const timer = setTimeout(() => {
      setFilters((prev) => ({ ...prev, search: inputSearch, page: 1 }));
    }, 400);
    return () => clearTimeout(timer);
  }, [inputSearch]);

  // Modal state
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [selectedUsuario, setSelectedUsuario] = useState<Usuario | undefined>();
  const [resetPasswordUser, setResetPasswordUser] = useState<{
    id: number;
    nombre: string;
  } | null>(null);

  const { data, isLoading, error } = useUsuarios(filters);
  const deleteMutation = useDeleteUsuario();
  const restoreMutation = useRestoreUsuario();

  // Confirm dialog state (reemplazo de borrado directo sin confirmación)
  const [confirmDialog, setConfirmDialog] = useState<ConfirmState | null>(null);
  const [isConfirmLoading, setIsConfirmLoading] = useState(false);

  const handleConfirmAccept = async () => {
    if (!confirmDialog) return;
    setIsConfirmLoading(true);
    try {
      await confirmDialog.onConfirm();
    } finally {
      setIsConfirmLoading(false);
      setConfirmDialog(null);
    }
  };

  // Borrado real: await para poder cerrar el diálogo al terminar y toast de
  // éxito contextual. El error lo maneja el onError del hook (catch vacío).
  const runEliminar = async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('Usuario eliminado');
    } catch {
      // El feedback de error ya lo emite useDeleteUsuario (onError → toast.error).
    }
  };

  // El ítem "Eliminar" del dropdown ahora abre la confirmación destructiva.
  const askEliminar = (usuario: UsuarioListItem) => {
    setConfirmDialog({
      title: ELIMINAR_DIALOG.title,
      message: ELIMINAR_DIALOG.message,
      confirmLabel: ELIMINAR_DIALOG.confirmLabel,
      variant: 'destructive',
      onConfirm: () => runEliminar(usuario.id),
    });
  };

  // Modal handlers
  const handleCreate = () => {
    setSelectedUsuario(undefined);
    setIsFormOpen(true);
  };

  const handleEdit = (usuario: UsuarioListItem) => {
    // Need to fetch full usuario data for edit
    setSelectedUsuario(usuario as Usuario);
    setIsFormOpen(true);
  };

  const handleCloseForm = () => {
    setIsFormOpen(false);
    setSelectedUsuario(undefined);
  };

  const handleResetPassword = (id: number, nombre: string) => {
    setResetPasswordUser({ id, nombre });
  };

  const handleCloseResetPassword = () => {
    setResetPasswordUser(null);
  };

  // Filter options
  const rolOptions: SelectOption[] = [
    { value: 'TODOS', label: 'Todos los roles' },
    { value: 'ADMIN', label: 'Administrador' },
    { value: 'COORDINADOR', label: 'Coordinador' },
    { value: 'TUTOR', label: 'Tutor' },
  ];

  const estadoOptions: SelectOption[] = [
    { value: 'TODOS', label: 'Todos los estados' },
    { value: 'true', label: 'Activos' },
    { value: 'false', label: 'Eliminados' },
  ];

  // Menu de acciones reutilizado en la tabla (desktop) y en la tarjeta (mobile).
  const renderActions = (usuario: UsuarioListItem) => (
    <Dropdown
      trigger={
        <button
          type="button"
          aria-label="Acciones"
          className="inline-flex items-center justify-center min-h-11 min-w-11 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted touch-manipulation"
        >
          <MoreVertical className="w-5 h-5" />
        </button>
      }
      items={[
        {
          label: 'Editar',
          onClick: () => handleEdit(usuario),
          icon: <Pencil className="w-4 h-4" />,
        },
        {
          label: 'Resetear contraseña',
          onClick: () => handleResetPassword(usuario.id, usuario.nombre),
          icon: <Key className="w-4 h-4" />,
        },
        usuario.activo
          ? {
            label: 'Eliminar',
            onClick: () => askEliminar(usuario),
            icon: <Trash2 className="w-4 h-4" />,
            variant: 'danger' as const,
          }
          : {
            label: 'Restaurar',
            onClick: () => restoreMutation.mutate(usuario.id),
            icon: <RotateCcw className="w-4 h-4" />,
          },
      ]}
    />
  );

  // Table columns
  const columns: TableColumn<UsuarioListItem>[] = [
    {
      key: 'nombre',
      header: 'Nombre',
      render: (usuario) => (
        <div>
          <div className="font-medium text-foreground">{usuario.nombre}</div>
          <div className="text-sm text-muted-foreground">@{usuario.username}</div>
        </div>
      ),
    },
    {
      key: 'rol',
      header: 'Rol',
      render: (usuario) => (
        <Badge variant={rolVariants[usuario.rol]}>
          {rolLabels[usuario.rol]}
        </Badge>
      ),
    },
    {
      key: 'activo',
      header: 'Estado',
      render: (usuario) => (
        <Badge variant={usuario.activo ? 'success' : 'default'}>
          {usuario.activo ? 'Activo' : 'Eliminado'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Fecha creación',
      render: (usuario) => (
        <span className="text-muted-foreground">
          {formatDate(usuario.created_at)}
        </span>
      ),
    },
    {
      key: 'last_login',
      header: 'Último acceso',
      render: (usuario) => (
        <span className="text-muted-foreground">
          {usuario.last_login ? formatDate(usuario.last_login) : 'Nunca'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Acciones',
      className: 'text-right',
      sticky: true,
      render: (usuario) => renderActions(usuario),
    },
  ];

  // Tarjeta mobile: nombre/rol/estado arriba, acciones a la derecha; fechas debajo.
  const renderCard = (usuario: UsuarioListItem) => (
    <div className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium text-foreground truncate">{usuario.nombre}</div>
          <div className="text-sm text-muted-foreground truncate">
            @{usuario.username}
          </div>
        </div>
        <div className="shrink-0 -mr-2 -mt-2">{renderActions(usuario)}</div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={rolVariants[usuario.rol]}>{rolLabels[usuario.rol]}</Badge>
        <Badge variant={usuario.activo ? 'success' : 'default'}>
          {usuario.activo ? 'Activo' : 'Eliminado'}
        </Badge>
      </div>

      <dl className="flex flex-col gap-1 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Creado</dt>
          <dd className="text-foreground text-right">
            {formatDate(usuario.created_at)}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted-foreground">Último acceso</dt>
          <dd className="text-foreground text-right">
            {usuario.last_login ? formatDate(usuario.last_login) : 'Nunca'}
          </dd>
        </div>
      </dl>
    </div>
  );

  // Handle filter changes


  const handleRolChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      rol: value as RolEnum | 'TODOS',
      page: 1,
    }));
  };

  const handleEstadoChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      activo: value === 'TODOS' ? 'TODOS' : value === 'true',
      page: 1,
    }));
  };

  // Loading state
  if (isLoading) {
    return <LoadingState title="Cargando usuarios…" />;
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-destructive mb-4">Error al cargar usuarios</div>
        <p className="text-muted-foreground mb-4">
          {error instanceof Error ? error.message : 'Error desconocido'}
        </p>
        <Button onClick={() => window.location.reload()}>Reintentar</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Usuarios</h1>
            <HelpButton title="Ayuda — Usuarios" content={helpContent.usuarios} />
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Gestiona los usuarios del sistema
          </p>
        </div>
        <Button onClick={handleCreate} className="w-full sm:w-auto">
          + Crear Usuario
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-card rounded-lg border border-border p-4 sm:p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          <Input
            label="Buscar"
            placeholder="Buscar por nombre o username..."
            value={inputSearch}
            onChange={(e) => setInputSearch(e.target.value)}
            inputMode="search"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
          <Select
            label="Rol"
            options={rolOptions}
            value={String(filters.rol)}
            onChange={(e) => handleRolChange(e.target.value)}
          />
          <Select
            label="Estado"
            options={estadoOptions}
            value={
              filters.activo === 'TODOS'
                ? 'TODOS'
                : String(filters.activo)
            }
            onChange={(e) => handleEstadoChange(e.target.value)}
          />
        </div>
      </div>

      {/* Results summary */}
      {data?.items && data.items.length > 0 && (
        <div className="text-sm text-muted-foreground">
          Mostrando {data.items.length} de {data.total} usuarios
        </div>
      )}

      {/* Table (desktop) / Cards (mobile) */}
      {data?.items && data.items.length > 0 ? (
        // Frame de card solo en desktop: en mobile cada fila ya es su propia card.
        <div className="lg:bg-card lg:rounded-lg lg:border lg:border-border lg:overflow-hidden">
          <ResponsiveTable
            columns={columns}
            data={data.items}
            keyExtractor={(item) => item.id}
            renderCard={renderCard}
          />
        </div>
      ) : (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <EmptyState
            icon="👥"
            title="No hay usuarios"
            description="No se encontraron usuarios con los filtros aplicados"
            action={
              inputSearch || filters.rol !== 'TODOS' || filters.activo !== 'TODOS' ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setInputSearch('');
                    setFilters({
                      rol: 'TODOS',
                      activo: 'TODOS',
                      search: '',
                      page: 1,
                      per_page: 20,
                    });
                  }}
                >
                  Limpiar filtros
                </Button>
              ) : undefined
            }
          />
        </div>
      )}

      {/* Pagination */}
      {data && data.total > data.per_page && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="secondary"
            disabled={filters.page === 1}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page! - 1 }))
            }
            className="flex-1 sm:flex-none min-h-11"
          >
            ← Anterior
          </Button>
          <div className="flex items-center px-2 sm:px-4 text-center text-sm text-muted-foreground shrink-0">
            Página {filters.page} de {Math.ceil(data.total / data.per_page)}
          </div>
          <Button
            variant="secondary"
            disabled={filters.page! >= Math.ceil(data.total / data.per_page)}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page! + 1 }))
            }
            className="flex-1 sm:flex-none min-h-11"
          >
            Siguiente →
          </Button>
        </div>
      )}

      {/* Modals */}
      <UsuarioForm
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        usuario={selectedUsuario}
      />

      {resetPasswordUser && (
        <ResetPasswordModal
          isOpen={!!resetPasswordUser}
          onClose={handleCloseResetPassword}
          usuarioId={resetPasswordUser.id}
          usuarioNombre={resetPasswordUser.nombre}
        />
      )}

      {/* Confirm Dialog (reemplazo del borrado directo sin confirmación) */}
      {confirmDialog && (
        <ConfirmDialog
          isOpen={true}
          onClose={() => {
            if (!isConfirmLoading) setConfirmDialog(null);
          }}
          onConfirm={handleConfirmAccept}
          title={confirmDialog.title}
          message={confirmDialog.message}
          confirmLabel={confirmDialog.confirmLabel}
          variant={confirmDialog.variant}
          isLoading={isConfirmLoading}
        />
      )}
    </div>
  );
};

