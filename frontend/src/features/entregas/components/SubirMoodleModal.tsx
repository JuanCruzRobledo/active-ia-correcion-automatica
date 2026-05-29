import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Send, AlertTriangle, AlertCircle } from 'lucide-react';

import { Modal } from '@/shared/components/ui/Modal';
import { Spinner } from '@/shared/components/ui';
import { moodleGradeService } from '../services/moodle-grade.service';

interface SubirMoodleModalProps {
  entregaId: number;
  alumno: string;
  isOpen: boolean;
  onClose: () => void;
}

function getErrorMessage(err: unknown): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail ?? e?.message ?? 'Ocurrió un error inesperado';
}

export function SubirMoodleModal({ entregaId, alumno, isOpen, onClose }: SubirMoodleModalProps) {
  const queryClient = useQueryClient();
  const [comentario, setComentario] = useState('');
  const [forzar, setForzar] = useState(false);

  const previewQuery = useQuery({
    queryKey: ['moodle-preview', entregaId],
    queryFn: () => moodleGradeService.getPreviewByEntrega(entregaId),
    enabled: isOpen,
    staleTime: 0,
    retry: false,
  });

  const preview = previewQuery.data?.preview;

  // Precargar el comentario sugerido cuando llega el preview
  useEffect(() => {
    if (preview) {
      setComentario(preview.comentario_sugerido);
      setForzar(false);
    }
  }, [preview]);

  const mutation = useMutation({
    mutationFn: () =>
      moodleGradeService.subir(previewQuery.data!.correccionId, comentario, forzar),
    onSuccess: (res) => {
      toast.success(`Corrección enviada a Moodle (${res.nota_enviada ?? res.estado})`);
      queryClient.invalidateQueries({ queryKey: ['entregas'] });
      onClose();
    },
    onError: (err) => {
      toast.error(getErrorMessage(err));
    },
  });

  const handleClose = () => {
    mutation.reset();
    onClose();
  };

  const enviarDisabled =
    !preview ||
    mutation.isPending ||
    (preview.requiere_comentario_tutor && !comentario.trim()) ||
    (preview.ya_enviada && !forzar);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={`Subir corrección a Moodle — ${alumno}`}
      size="lg"
      footer={
        <>
          <button
            onClick={handleClose}
            className="cursor-pointer rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            Cancelar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={enviarDisabled}
            className="flex cursor-pointer items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending ? <Spinner size="sm" /> : <Send className="h-4 w-4" />}
            Enviar corrección
          </button>
        </>
      }
    >
      {previewQuery.isLoading && (
        <div className="flex flex-col items-center gap-3 py-8">
          <Spinner />
          <p className="text-sm text-muted-foreground">Calculando lo que se enviará a Moodle…</p>
        </div>
      )}

      {previewQuery.isError && (
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <AlertCircle className="h-10 w-10 text-destructive" />
          <p className="font-semibold text-foreground">No se puede enviar</p>
          <p className="text-sm text-muted-foreground">{getErrorMessage(previewQuery.error)}</p>
        </div>
      )}

      {preview && (
        <div className="space-y-4">
          {/* Nota que se enviará */}
          <div className="flex items-center justify-between rounded-md border border-border bg-muted/20 px-4 py-3">
            <span className="text-sm text-muted-foreground">Nota que se enviará a Moodle</span>
            <span className="text-lg font-bold text-foreground">{preview.nota_a_enviar}</span>
          </div>

          {/* Aviso de re-envío */}
          {preview.ya_enviada && (
            <label className="flex items-start gap-2 rounded-md bg-warning/10 px-3 py-2 text-sm text-warning">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="flex-1">
                Esta corrección ya fue enviada a Moodle.
                <span className="mt-1 flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={forzar}
                    onChange={(e) => setForzar(e.target.checked)}
                    className="cursor-pointer"
                  />
                  Reenviar de todas formas
                </span>
              </span>
            </label>
          )}

          {/* Comentario editable */}
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground">
              Comentario para el alumno
              {preview.requiere_comentario_tutor && (
                <span className="ml-1 text-xs text-destructive">(obligatorio)</span>
              )}
            </label>
            <textarea
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
              rows={6}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder={
                preview.requiere_comentario_tutor
                  ? 'Escribí tu comentario de evaluación…'
                  : 'Comentario a publicar en Moodle'
              }
            />
            {preview.requiere_comentario_tutor && !comentario.trim() && (
              <p className="text-xs text-destructive">
                Para esta rúbrica debés escribir un comentario antes de enviar.
              </p>
            )}
          </div>

          {/* El cierre con el link se agrega automáticamente como hipervínculo */}
          <p className="rounded-md bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            Al final se agregará automáticamente: <span className="text-foreground">Te dejo tu{' '}</span>
            <a
              href={preview.link_devolucion}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-primary underline"
            >
              devolución
            </a>
            <span className="block text-[11px] opacity-80">
              (la palabra “devolución” es el enlace al PDF y abre en una pestaña nueva)
            </span>
          </p>
        </div>
      )}
    </Modal>
  );
}
