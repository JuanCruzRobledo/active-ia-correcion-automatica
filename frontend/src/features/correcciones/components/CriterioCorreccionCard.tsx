import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { Badge } from '../../../shared/components/ui/Badge';
import { Select } from '../../../shared/components/ui/Select';
import type { CriterioEvaluado, EstadoCriterio } from '../types';
import { SubcriterioEditor } from './SubcriterioEditor';

interface CriterioCorreccionCardProps {
  criterio: CriterioEvaluado;
  isViewMode: boolean;
  errors: Record<string, string>;
  onChange: (id: string, field: keyof CriterioEvaluado, value: string | number) => void;
  onSubChange: (criterioId: string, subId: string, field: 'puntaje_obtenido' | 'feedback', value: string | number) => void;
}
const estados: { value: EstadoCriterio; label: string }[] = [
  { value: 'OK', label: 'OK' }, { value: 'WARNING', label: 'Warning' }, { value: 'ERROR', label: 'Error' },
];
const config = {
  OK: { icon: CheckCircle2, variant: 'success', css: 'bg-success/10 border-success/30' },
  WARNING: { icon: AlertTriangle, variant: 'warning', css: 'bg-warning/10 border-warning/30' },
  ERROR: { icon: XCircle, variant: 'destructive', css: 'bg-destructive/10 border-destructive/30' },
} as const;

export function CriterioCorreccionCard({ criterio: c, isViewMode, errors, onChange, onSubChange }: CriterioCorreccionCardProps) {
  const status = config[c.estado]; const Icon = status.icon;
  const hasSubs = Boolean(c.subcriterios_evaluados?.length);
  const scoreId = `${c.id}-puntaje`; const feedbackId = `${c.id}-feedback`;
  return (
    <div className={`rounded-lg border p-4 space-y-3 ${status.css}`}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-medium flex items-center gap-2"><Icon className="h-5 w-5" />{c.nombre}</h4>
        <Badge variant={status.variant}>{c.estado}</Badge>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label htmlFor={scoreId} className="block text-xs text-muted-foreground mb-1.5">Puntaje {c.id}</label>
          {isViewMode || hasSubs ? <div className="text-lg font-semibold">{Number.isFinite(c.puntaje_obtenido) ? c.puntaje_obtenido : '—'} / {c.puntaje_maximo}</div> :
            <Select id={scoreId} value={c.puntaje_obtenido.toString()}
              onChange={e => onChange(c.id, 'puntaje_obtenido', Number(e.target.value))}
              options={Array.from({ length: Math.floor(c.puntaje_maximo) + 1 }, (_, i) => ({ value: String(i), label: String(i) }))} />}
          {!isViewMode && hasSubs && <p className="text-xs text-muted-foreground">Total del desglose; modificá los subcriterios.</p>}
        </div>
        <div><label htmlFor={`${c.id}-estado`} className="block text-xs text-muted-foreground mb-1.5">Estado</label>
          {isViewMode ? <p>{c.estado}</p> : <Select id={`${c.id}-estado`} value={c.estado} options={estados}
            onChange={e => onChange(c.id, 'estado', e.target.value)} />}
        </div>
      </div>
      <div><label htmlFor={feedbackId} className="block text-xs text-muted-foreground mb-1.5">Feedback {c.id}</label>
        <textarea id={feedbackId} value={c.feedback} disabled={isViewMode} rows={3}
          onChange={e => onChange(c.id, 'feedback', e.target.value)}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm disabled:bg-muted/30" />
      </div>
      {errors[c.id] && !isViewMode && <p role="alert" className="text-sm text-destructive">{errors[c.id]}</p>}
      {hasSubs && <div className="border-t border-border/50 pt-3 space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Desglose por subcriterio</p>
        {c.subcriterios_evaluados!.map(sub => <SubcriterioEditor key={sub.id} subcriterio={sub} criterioId={c.id}
          isViewMode={isViewMode} error={errors[`${c.id}/${sub.id}`]}
          onChange={(id, field, value) => onSubChange(c.id, id, field, value)} />)}
      </div>}
    </div>
  );
}
