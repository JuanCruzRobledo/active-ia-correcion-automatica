/**
 * useLogin Hook
 *
 * Provides mutation for user login with React Query.
 * Handles login request, token storage, and navigation.
 *
 * Ref: skills/react-typescript/SKILL.md
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-AUTH-01
 */

import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { AxiosError } from 'axios';
import { login } from '../services/auth-service';
import type { LoginRequest, LoginResponse } from '@/shared/types';
import { getErrorMessage } from '@/shared/types';

/**
 * Hook for user login with React Query mutation.
 *
 * @returns React Query mutation object
 *
 * @example
 * ```tsx
 * function LoginForm() {
 *   const loginMutation = useLogin();
 *
 *   const handleSubmit = (data: LoginRequest) => {
 *     loginMutation.mutate(data);
 *   };
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <Input name="username" />
 *       <Input name="password" type="password" />
 *       <Button type="submit" loading={loginMutation.isPending}>
 *         Iniciar sesión
 *       </Button>
 *       {loginMutation.isError && (
 *         <Alert variant="destructive">{loginMutation.error.message}</Alert>
 *       )}
 *     </form>
 *   );
 * }
 * ```
 */
export function useLogin() {
  const navigate = useNavigate();

  return useMutation<LoginResponse, Error, LoginRequest>({
    mutationFn: login,

    onSuccess: (data) => {
      // Show success message
      toast.success(`¡Bienvenido, ${data.user.nombre}!`);

      // Check if user needs to change password (first login)
      if (data.user.primer_login) {
        // Redirect to change password page/modal
        navigate('/change-password', { replace: true });
      } else {
        // Redirect to dashboard
        navigate('/dashboard', { replace: true });
      }
    },

    onError: (error) => {
      // getErrorMessage sabe extraer `detail` (string o array) del CUERPO de la
      // respuesta; le pasamos `error.response.data`, no el AxiosError crudo (cuyo
      // `.message` sería "Request failed with status code 401").
      const responseData =
        error instanceof AxiosError ? error.response?.data : undefined;
      const message = getErrorMessage(responseData ?? error);

      // ERR-004: para el 401 de credenciales el interceptor global ya NO notifica
      // (lo deja pasar), así que lo surfaceamos acá con el mensaje real del backend.
      // El resto de los estados (403 cuenta bloqueada, 422, 5xx, red) los notifica
      // el interceptor, así que NO duplicamos el toast.
      if (error instanceof AxiosError && error.response?.status === 401) {
        toast.error(message);
      }

      console.error('[Login Error]', message);
    },
  });
}
