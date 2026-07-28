/**
 * useSeleccionarUniversidad Hook
 *
 * Segundo paso del login en dos pasos (Fase 5 multi-tenant): cuando
 * `useLogin` devuelve `requiere_seleccion: true`, este hook completa el
 * inicio de sesión llamando a `POST /auth/select-universidad` con el
 * `token_transicion` y la universidad elegida.
 *
 * Mismo comportamiento de éxito que `useLogin` (toast de bienvenida +
 * navegación a `/change-password` o `/dashboard` según `primer_login`), pero
 * SIN mostrar toast de error genérico: el 401 de token de transición vencido
 * lo maneja `LoginPage` (vuelve al formulario), no un toast.
 */
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { seleccionarUniversidad } from '../services/auth-service';
import type { LoginResponse } from '@/shared/types';

interface SeleccionarUniversidadInput {
  tokenTransicion: string;
  universidadId: number;
}

export function useSeleccionarUniversidad() {
  const navigate = useNavigate();

  return useMutation<LoginResponse, Error, SeleccionarUniversidadInput>({
    mutationFn: ({ tokenTransicion, universidadId }) =>
      seleccionarUniversidad(tokenTransicion, universidadId),

    onSuccess: (data) => {
      toast.success(`¡Bienvenido, ${data.user.nombre}!`);

      if (data.user.primer_login) {
        navigate('/change-password', { replace: true });
      } else {
        navigate('/dashboard', { replace: true });
      }
    },
  });
}
