import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Sparkles } from 'lucide-react';

import { useProfile } from '@/features/perfil/hooks/usePerfil';
import { Spinner } from '@/shared/components/ui';
import { getProgresoGlobal, corregirGlobal } from '../services/correccion-global.service';

function getErrorMessage(err: unknown): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail ?? e?.message ?? 'Ocurrió un error inesperado';
}

/**
 * Banner "Corregir todo" — corrección masiva global para tutores con API key paga.
 * Visible sólo si gemini_api_key_paga y hay entregas SUBIDA. Hace polling del progreso.
 */
export function CorregirTodoButton() {
  const { data: profile } = useProfile();
  const queryClient = useQueryClient();
  const [enProceso, setEnProceso] = useState(false);

  const esPaga = !!profile?.gemini_api_key_paga;

  const progresoQuery = useQuery({
    queryKey: ['progreso-global'],
    queryFn: getProgresoGlobal,
    enabled: esPaga,
    // El conteo de SUBIDA cambia desde OTRAS pantallas (importar pendientes, subir
    // entregas, corregir). El staleTime global de 5min haría que al volver al
    // dashboard se sirva un conteo viejo (subidas=0) y el botón no aparezca hasta
    // refrescar la página. Como este botón es el ÚNICO consumidor de 'progreso-global'
    // y sólo vive en el dashboard, revalidar en cada montaje (cada visita al dashboard)
    // mantiene el conteo fresco sin acoplar 11 mutaciones a esta query key.
    staleTime: 0,
    refetchOnMount: 'always',
    refetchInterval: enProceso ? 10000 : false,
  });

  const prog = progresoQuery.data;
  const subidas = prog?.subidas ?? 0;

  const mutation = useMutation({
    mutationFn: corregirGlobal,
    onSuccess: (res) => {
      if (res.total_encoladas > 0) {
        toast.success(`Corrección iniciada para ${res.total_encoladas} entrega(s).`);
        setEnProceso(true);
        queryClient.invalidateQueries({ queryKey: ['progreso-global'] });
      } else {
        toast('No hay entregas pendientes para corregir.');
      }
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  });

  // Detener el polling cuando ya no quedan SUBIDA ni PENDIENTE.
  useEffect(() => {
    if (enProceso && prog && prog.subidas === 0 && prog.pendientes === 0) {
      setEnProceso(false);
      toast.success('Corrección masiva finalizada.');
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    }
  }, [enProceso, prog, queryClient]);

  // No mostrar si no es paga, o si no hay nada por corregir y no está procesando.
  if (!esPaga) return null;
  if (subidas === 0 && !enProceso) return null;

  return (
    <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 px-5 py-4">
      <div className="flex items-center gap-3">
        <Sparkles className="h-5 w-5 text-primary" />
        <div className="text-sm">
          {enProceso ? (
            <p className="font-medium text-foreground">
              Corrigiendo en segundo plano…{' '}
              <span className="text-muted-foreground">
                {prog?.corregidas ?? 0} corregidas · {prog?.pendientes ?? 0} en proceso ·{' '}
                {subidas} en cola
              </span>
            </p>
          ) : (
            <p className="font-medium text-foreground">
              Tenés <span className="font-bold text-primary">{subidas}</span> entrega
              {subidas !== 1 ? 's' : ''} por corregir.
            </p>
          )}
        </div>
      </div>

      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending || enProceso}
        className="flex cursor-pointer items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {(mutation.isPending || enProceso) && <Spinner size="sm" />}
        Corregir todo (API Key paga)
      </button>
    </div>
  );
}
