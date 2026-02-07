# Frontend Rules - Active-IA

## Stack

- React 18 + TypeScript (strict)
- Vite
- Tailwind CSS
- React Router 6
- React Query (@tanstack/react-query)
- React Hook Form + Zod
- Axios
- Lucide React (iconos)

## Estructura de Componentes

```typescript
// SIEMPRE: Props tipadas con interface
interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
}

// SIEMPRE: Componente funcional con destructuring
export const Button = ({
  label,
  onClick,
  variant = 'primary',
  disabled = false
}: ButtonProps) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'px-4 py-2 rounded-md font-medium',
        variant === 'primary' && 'bg-blue-600 text-white',
        variant === 'secondary' && 'bg-gray-200 text-gray-800',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      {label}
    </button>
  );
};
```

## React Query para Estado del Servidor

```typescript
// Hook para listar
export const useUsuarios = () => {
  return useQuery({
    queryKey: ['usuarios'],
    queryFn: usuariosService.getAll,
  });
};

// Hook para crear
export const useCreateUsuario = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: usuariosService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usuarios'] });
    },
  });
};

// Uso en componente
const UsuariosPage = () => {
  const { data: usuarios, isLoading, error } = useUsuarios();
  const createMutation = useCreateUsuario();

  if (isLoading) return <Spinner />;
  if (error) return <Error message={error.message} />;

  return <UsuariosList usuarios={usuarios} />;
};
```

## Services para API

```typescript
// shared/services/usuarios-service.ts
import { apiClient } from './api-client';
import type { Usuario, UsuarioCreate } from '../types';

export const usuariosService = {
  getAll: () => apiClient.get<Usuario[]>('/usuarios').then(r => r.data),
  getById: (id: number) => apiClient.get<Usuario>(`/usuarios/${id}`).then(r => r.data),
  create: (data: UsuarioCreate) => apiClient.post<Usuario>('/usuarios', data).then(r => r.data),
  update: (id: number, data: Partial<Usuario>) => apiClient.put<Usuario>(`/usuarios/${id}`, data).then(r => r.data),
  delete: (id: number) => apiClient.delete(`/usuarios/${id}`),
};
```

## Tailwind - Mobile First

```typescript
// SIEMPRE: Mobile first, luego breakpoints mayores
<div className="
  flex flex-col gap-4          // Mobile: columna
  md:flex-row md:gap-6         // Tablet: fila
  lg:gap-8                     // Desktop: mas espacio
">
```

## Decision Tree: Donde poner estado

| Situacion | Solucion |
|-----------|----------|
| Datos del servidor | React Query |
| Form local | useState o React Hook Form |
| UI global (theme, sidebar) | Context |
| Estado derivado costoso | useMemo |
| Callback memoizado | useCallback |

## NUNCA hacer esto

```typescript
// MAL - class component
class MyComponent extends Component { }  // NO!

// MAL - any
const data: any = response;  // NO! Usar tipos

// MAL - mutar estado
state.push(item);  // NO! Usar setState([...state, item])

// MAL - fetch en componente
useEffect(() => {
  fetch('/api/...').then(...)  // NO! Usar React Query
}, []);

// MAL - useEffect sin deps
useEffect(() => { ... });  // NO! Siempre poner []
```
