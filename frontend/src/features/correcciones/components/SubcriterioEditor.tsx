import type { SubcriterioEvaluado } from '../types';
import { Input } from '../../../shared/components/ui/Input';

interface SubcriterioEditorProps {
  subcriterio: SubcriterioEvaluado;
  criterioId: string;
  isViewMode: boolean;
  error?: string;
  onChange: (id: string, field: 'puntaje_obtenido' | 'feedback', value: string | number) => void;
}

export function SubcriterioEditor({ subcriterio: sub, criterioId, isViewMode, error, onChange }: SubcriterioEditorProps) {
  const commentId = `${criterioId}-${sub.id}-comentario`;
  return (
    <div className="rounded-md bg-background/60 border border-border/50 p-3 text-xs space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{sub.id}</span>
        <span className="text-muted-foreground">{sub.estado}</span>
      </div>
      {isViewMode ? <>
        <p>{sub.puntaje_obtenido} / {sub.puntaje_maximo}</p>
        <p className="text-muted-foreground">{sub.feedback}</p>
      </> : <>
        <Input type="number" step="any" min={0} max={sub.puntaje_maximo}
          label={`Puntaje ${sub.id}`} value={Number.isFinite(sub.puntaje_obtenido) ? sub.puntaje_obtenido : ''}
          onChange={e => onChange(sub.id, 'puntaje_obtenido', e.target.value === '' ? NaN : Number(e.target.value))}
          helperText={`Máximo: ${sub.puntaje_maximo}`} aria-invalid={Boolean(error)} />
        <label htmlFor={commentId} className="block font-medium">Comentario {sub.id}</label>
        <textarea id={commentId} value={sub.feedback} rows={3}
          onChange={e => onChange(sub.id, 'feedback', e.target.value)}
          aria-invalid={Boolean(error)} aria-describedby={error ? `${commentId}-error` : undefined}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-ring" />
        {error && <p id={`${commentId}-error`} role="alert" className="text-destructive">{error}</p>}
      </>}
    </div>
  );
}
