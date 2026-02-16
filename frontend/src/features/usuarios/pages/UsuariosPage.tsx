// features/usuarios/pages/UsuariosPage.tsx
/**
 * Usuarios management page for Admin role
 * 
 * Displays table of users with filters and CRUD actions
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 3
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { useState } from 'react';
import { Pencil, Key, Trash2, RotateCcw } from 'lucide-react';
import { useUsuarios, useDeleteUsuario, useRestoreUsuario } from '../hooks';
import { UsuarioForm, ResetPasswordModal } from '../components';
import type { Usuario, UsuarioListItem } from '../types';
import type { RolEnum, UsuariosFilters } from '../types';
import {
  Button,
  Input,
  Select,
  Badge,
  Table,
  Spinner,
  EmptyState,
  Dropdown,
  type TableColumn,
  type SelectOption,
} from '@/shared/components/ui';
import { formatDate } from '@/shared/utils';

export const UsuariosPage = () => {
  const [filters, setFilters] = useState<UsuariosFilters>({
    rol: 'TODOS',
    activo: 'TODOS',
    search: '',
    page: 1,
    per_page: 20,
  });

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

  // Debug
  console.log('UsuariosPage state:', { data, isLoading, error });


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

  // Table columns
  const columns: TableColumn<UsuarioListItem>[] = [
    {
      key: 'nombre',
      header: 'Nombre',
      render: (usuario) => (
        <div>
          <div className="font-medium text-gray-900">{usuario.nombre}</div>
          <div className="text-sm text-gray-500">@{usuario.username}</div>
        </div>
      ),
    },
    {
      key: 'rol',
      header: 'Rol',
      render: (usuario) => {
        const rolVariants: Record<RolEnum, 'destructive' | 'info' | 'success'> = {
          ADMIN: 'destructive',
          COORDINADOR: 'info',
          TUTOR: 'success',
        };
        const rolLabels: Record<RolEnum, string> = {
          ADMIN: 'Administrador',
          COORDINADOR: 'Coordinador',
          TUTOR: 'Tutor',
        };
        return (
          <Badge variant={rolVariants[usuario.rol]}>
            {rolLabels[usuario.rol]}
          </Badge>
        );
      },
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
        <span className="text-gray-500">
          {formatDate(usuario.created_at)}
        </span>
      ),
    },
    {
      key: 'last_login',
      header: 'Último acceso',
      render: (usuario) => (
        <span className="text-gray-500">
          {usuario.last_login ? formatDate(usuario.last_login) : 'Nunca'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Acciones',
      className: 'text-right',
      sticky: true,
      render: (usuario) => (
        <Dropdown
          trigger={
            <button className="text-gray-400 hover:text-gray-600 px-2 py-1">
              •••
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
                onClick: () => deleteMutation.mutate(usuario.id),
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
      ),
    },
  ];

  // Handle filter changes
  const handleSearchChange = (value: string) => {
    setFilters((prev) => ({ ...prev, search: value, page: 1 }));
  };

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
    return (
      <div className="flex justify-center items-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <div className="text-red-600 mb-4">Error al cargar usuarios</div>
        <p className="text-gray-500 mb-4">
          {error instanceof Error ? error.message : 'Error desconocido'}
        </p>
        <Button onClick={() => window.location.reload()}>Reintentar</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Usuarios</h1>
          <p className="text-sm text-gray-500 mt-1">
            Gestiona los usuarios del sistema
          </p>
        </div>
        <Button onClick={handleCreate}>
          + Crear Usuario
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            label="Buscar"
            placeholder="Buscar por nombre o username..."
            value={filters.search}
            onChange={(e) => handleSearchChange(e.target.value)}
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
        <div className="text-sm text-gray-500">
          Mostrando {data.items.length} de {data.total} usuarios
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {data?.items && data.items.length > 0 ? (
          <Table
            columns={columns}
            data={data.items}
            keyExtractor={(item) => item.id}
          />
        ) : (
          <EmptyState
            icon="👥"
            title="No hay usuarios"
            description="No se encontraron usuarios con los filtros aplicados"
            action={
              filters.search || filters.rol !== 'TODOS' || filters.activo !== 'TODOS' ? (
                <Button
                  variant="secondary"
                  onClick={() =>
                    setFilters({
                      rol: 'TODOS',
                      activo: 'TODOS',
                      search: '',
                      page: 1,
                      per_page: 20,
                    })
                  }
                >
                  Limpiar filtros
                </Button>
              ) : undefined
            }
          />
        )}
      </div>

      {/* Pagination */}
      {data && data.total > data.per_page && (
        <div className="flex justify-center gap-2">
          <Button
            variant="secondary"
            disabled={filters.page === 1}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page! - 1 }))
            }
          >
            ← Anterior
          </Button>
          <div className="flex items-center px-4 text-sm text-gray-600">
            Página {filters.page} de {Math.ceil(data.total / data.per_page)}
          </div>
          <Button
            variant="secondary"
            disabled={filters.page! >= Math.ceil(data.total / data.per_page)}
            onClick={() =>
              setFilters((prev) => ({ ...prev, page: prev.page! + 1 }))
            }
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
    </div>
  );
};

