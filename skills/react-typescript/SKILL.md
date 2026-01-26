---
name: react-typescript
description: >
  Patrones y convenciones para desarrollo frontend con React, TypeScript y Tailwind CSS.
  Trigger: Cuando trabajes con componentes React, hooks, servicios de API, o estilos.
metadata:
  author: Active-IA Team
  version: "1.0"
  scope: [root, frontend]
  auto_invoke:
    - "Creating React components"
    - "Writing React hooks"
    - "Styling with Tailwind"
    - "Managing state with React Query"
---

# React TypeScript Skill

## When to Use

- Creando componentes React
- Escribiendo hooks personalizados
- Integrando con APIs (React Query + Axios)
- Aplicando estilos con Tailwind CSS
- Definiendo tipos TypeScript

## Critical Patterns

### ALWAYS
- Componentes funcionales (nunca class components)
- Props tipadas con `interface` (no `type` para props)
- `useState` para estado local
- `useMemo` para valores derivados costosos
- `useCallback` para callbacks pasados a children
- React Query para estado del servidor
- Tailwind para estilos (mobile-first)
- Exports nombrados (no default exports)

### NEVER
- Class components
- `any` en TypeScript (usar `unknown` si es necesario)
- Mutar estado directamente
- `useEffect` sin dependency array
- Fetch directo en componentes (usar services/)
- CSS modules o styled-components
- Lógica de negocio en componentes

## Decision Trees

### ¿Dónde colocar el componente?

| Tipo | Ubicación |
|------|-----------|
| UI genérico (Button, Input, Modal) | `shared/components/ui/` |
| Layout (Header, Sidebar, Footer) | `shared/components/layout/` |
| Feature-specific | `features/{feature}/components/` |
| Página completa | `features/{feature}/pages/` |

### ¿Qué hook usar para estado?

| Situación | Hook |
|-----------|------|
| Estado local simple | `useState` |
| Estado local complejo | `useReducer` |
| Valor derivado costoso | `useMemo` |
| Callback memoizado | `useCallback` |
| Referencia a DOM | `useRef` |
| Estado global UI | Context + `useContext` |
| Estado del servidor | React Query |
| Formularios | React Hook Form |

### ¿Cómo estructurar un feature?

```
features/{name}/
├── components/       # Componentes específicos del feature
│   ├── EntregaCard.tsx
│   └── EntregaList.tsx
├── hooks/            # Hooks específicos
│   └── useEntregas.ts
├── services/         # Llamadas API
│   └── entregasService.ts
├── types/            # Tipos TypeScript
│   └── index.ts
├── pages/            # Páginas/vistas
│   └── EntregasPage.tsx
└── index.ts          # Exports públicos
```

## Code Examples

### Component con Props Tipadas

```tsx
// features/entregas/components/EntregaCard.tsx
import { Badge } from '@/shared/components/ui/Badge';
import { Button } from '@/shared/components/ui/Button';
import { formatDate } from '@/shared/utils/date';
import { Entrega, EstadoEntrega } from '../types';

interface EntregaCardProps {
  entrega: Entrega;
  onCorregir: (id: number) => void;
  onVerDetalle: (id: number) => void;
  isLoading?: boolean;
}

const estadoColors: Record<EstadoEntrega, string> = {
  SUBIDA: 'gray',
  PENDIENTE: 'yellow',
  CORREGIDA: 'green',
  ERROR: 'red',
};

export const EntregaCard = ({
  entrega,
  onCorregir,
  onVerDetalle,
  isLoading = false,
}: EntregaCardProps) => {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="font-medium text-gray-900">{entrega.alumno}</h3>
          <p className="text-sm text-gray-500">
            {formatDate(entrega.fechaSubida)}
          </p>
        </div>
        <Badge color={estadoColors[entrega.estado]}>
          {entrega.estado}
        </Badge>
      </div>

      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onVerDetalle(entrega.id)}
        >
          Ver detalle
        </Button>

        {entrega.estado === 'PENDIENTE' && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => onCorregir(entrega.id)}
            disabled={isLoading}
          >
            {isLoading ? 'Corrigiendo...' : 'Corregir'}
          </Button>
        )}
      </div>
    </div>
  );
};
```

### Custom Hook con React Query

```tsx
// features/entregas/hooks/useEntregas.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { entregasService } from '../services/entregasService';
import { CreateEntregaDTO, Entrega } from '../types';

export const useEntregas = (comisionId: number) => {
  return useQuery({
    queryKey: ['entregas', comisionId],
    queryFn: () => entregasService.getByComision(comisionId),
    staleTime: 5 * 60 * 1000, // 5 minutos
  });
};

export const useEntrega = (id: number) => {
  return useQuery({
    queryKey: ['entrega', id],
    queryFn: () => entregasService.getById(id),
    enabled: !!id,
  });
};

export const useCreateEntrega = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateEntregaDTO) => entregasService.create(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['entregas', variables.comisionId],
      });
    },
  });
};

export const useCorregirEntrega = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => entregasService.corregir(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['entregas'] });
      queryClient.setQueryData(['entrega', data.id], data);
    },
  });
};
```

### Service Layer

```tsx
// features/entregas/services/entregasService.ts
import { api } from '@/shared/services/api';
import { Entrega, CreateEntregaDTO, Correccion } from '../types';

export const entregasService = {
  getByComision: async (comisionId: number): Promise<Entrega[]> => {
    const { data } = await api.get(`/comisiones/${comisionId}/entregas`);
    return data;
  },

  getById: async (id: number): Promise<Entrega> => {
    const { data } = await api.get(`/entregas/${id}`);
    return data;
  },

  create: async (dto: CreateEntregaDTO): Promise<Entrega> => {
    const { data } = await api.post('/entregas', dto);
    return data;
  },

  upload: async (comisionId: number, file: File): Promise<Entrega[]> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post(
      `/comisiones/${comisionId}/entregas/upload`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return data;
  },

  corregir: async (id: number): Promise<Correccion> => {
    const { data } = await api.post(`/entregas/${id}/corregir`);
    return data;
  },

  corregirLote: async (ids: number[]): Promise<Correccion[]> => {
    const { data } = await api.post('/entregas/corregir-lote', { ids });
    return data;
  },
};
```

### Types

```tsx
// features/entregas/types/index.ts
export type EstadoEntrega = 'SUBIDA' | 'PENDIENTE' | 'CORREGIDA' | 'ERROR';

export interface Entrega {
  id: number;
  comisionId: number;
  alumno: string;
  archivo: string;
  codigoConsolidado: string;
  estado: EstadoEntrega;
  fechaSubida: string;
  correccion?: Correccion;
}

export interface CreateEntregaDTO {
  comisionId: number;
  alumno: string;
  archivo: File;
}

export interface Correccion {
  id: number;
  entregaId: number;
  nota: number;
  criterios: CriterioEvaluado[];
  fortalezas: string[];
  recomendaciones: string[];
  comentarioGeneral: string;
  fechaCorreccion: string;
  editadoManualmente: boolean;
}

export interface CriterioEvaluado {
  id: string;
  nombre: string;
  puntajeObtenido: number;
  puntajeMaximo: number;
  estado: 'OK' | 'WARNING' | 'ERROR';
  feedback: string;
}
```

### UI Component (Shared)

```tsx
// shared/components/ui/Button.tsx
import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/shared/utils/cn';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

const variants = {
  primary: 'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300',
  secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 disabled:bg-gray-50',
  danger: 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-300',
  ghost: 'bg-transparent hover:bg-gray-100 text-gray-700',
};

const sizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center font-medium rounded-lg',
          'transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
          'disabled:cursor-not-allowed',
          variants[variant],
          sizes[size],
          className
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && (
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
```

### Page Component

```tsx
// features/entregas/pages/EntregasPage.tsx
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useEntregas, useCorregirEntrega } from '../hooks/useEntregas';
import { EntregaCard } from '../components/EntregaCard';
import { UploadModal } from '../components/UploadModal';
import { Button } from '@/shared/components/ui/Button';
import { Spinner } from '@/shared/components/ui/Spinner';
import { EmptyState } from '@/shared/components/ui/EmptyState';

export const EntregasPage = () => {
  const { comisionId } = useParams<{ comisionId: string }>();
  const [showUpload, setShowUpload] = useState(false);

  const { data: entregas, isLoading, error } = useEntregas(Number(comisionId));
  const corregirMutation = useCorregirEntrega();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-red-600">
        Error al cargar entregas
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Entregas</h1>
        <Button onClick={() => setShowUpload(true)}>
          Cargar entregas
        </Button>
      </div>

      {entregas?.length === 0 ? (
        <EmptyState
          title="Sin entregas"
          description="No hay entregas cargadas en esta comisión"
          action={
            <Button onClick={() => setShowUpload(true)}>
              Cargar primera entrega
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {entregas?.map((entrega) => (
            <EntregaCard
              key={entrega.id}
              entrega={entrega}
              onCorregir={(id) => corregirMutation.mutate(id)}
              onVerDetalle={(id) => console.log('Ver detalle', id)}
              isLoading={corregirMutation.isPending}
            />
          ))}
        </div>
      )}

      <UploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        comisionId={Number(comisionId)}
      />
    </div>
  );
};
```

### Utility: cn (classnames)

```tsx
// shared/utils/cn.ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const cn = (...inputs: ClassValue[]) => {
  return twMerge(clsx(inputs));
};
```

## Tailwind Patterns

### Responsive Design (Mobile-first)

```tsx
// Base: mobile, md: tablet, lg: desktop
<div className="flex flex-col md:flex-row lg:gap-8">
  <aside className="w-full md:w-64 lg:w-72">Sidebar</aside>
  <main className="flex-1">Content</main>
</div>
```

### Dark Mode (si aplica)

```tsx
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100">
  Content
</div>
```

### Common Patterns

```tsx
// Card
<div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">

// Form input
<input className="w-full px-3 py-2 border border-gray-300 rounded-lg
  focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />

// Badge
<span className="inline-flex items-center px-2.5 py-0.5 rounded-full
  text-xs font-medium bg-green-100 text-green-800">

// Table
<table className="min-w-full divide-y divide-gray-200">
  <thead className="bg-gray-50">
    <tr>
      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500
        uppercase tracking-wider">
```

## Commands

```bash
# Desarrollo
npm run dev

# Build
npm run build

# Preview build
npm run preview

# Tests
npm run test

# Linting
npm run lint

# Type checking
npm run typecheck
```

## Resources

- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [React Query](https://tanstack.com/query/latest)
- [React Router](https://reactrouter.com/)
