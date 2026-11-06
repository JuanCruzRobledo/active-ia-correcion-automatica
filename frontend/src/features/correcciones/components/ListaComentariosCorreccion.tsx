import { useState } from 'react';
import { CheckCircle2, Lightbulb, Plus, X } from 'lucide-react';
import { Input } from '../../../shared/components/ui/Input';
import { Button } from '../../../shared/components/ui/Button';
import { Badge } from '../../../shared/components/ui/Badge';
import { AccordionItem, AccordionTrigger, AccordionContent } from '../../../shared/components/ui/Accordion';

interface ListaComentariosCorreccionProps {
  kind: 'fortalezas' | 'recomendaciones';
  items: string[];
  isViewMode: boolean;
  onChange: (items: string[]) => void;
}

export function ListaComentariosCorreccion({ kind, items, isViewMode, onChange }: ListaComentariosCorreccionProps) {
  const [draft, setDraft] = useState('');
  const strength = kind === 'fortalezas'; const Icon = strength ? CheckCircle2 : Lightbulb;
  const label = strength ? 'Fortalezas' : 'Recomendaciones';
  const add = () => { if (draft.trim()) { onChange([...items, draft.trim()]); setDraft(''); } };
  return <AccordionItem value={kind}>
    <AccordionTrigger value={kind} icon={<Icon className="h-5 w-5" />}
      badge={<Badge variant={strength ? 'success' : 'warning'} className="ml-2">{items.length}</Badge>}>{label}</AccordionTrigger>
    <AccordionContent value={kind}>
      {!isViewMode && <div className="flex gap-2 mb-4">
        <Input value={draft} onChange={e => setDraft(e.target.value)} aria-label={`Agregar ${label.toLowerCase()}`}
          placeholder={strength ? 'Agregar nueva fortaleza...' : 'Agregar nueva recomendación...'}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(); } }} />
        <Button variant="outline" size="sm" onClick={add} disabled={!draft.trim()} aria-label={`Agregar ${label.toLowerCase()}`}><Plus className="h-4 w-4" /></Button>
      </div>}
      {items.length ? <ul className="space-y-2">{items.map((item, index) => <li key={`${index}-${item}`}
        className={`flex items-start justify-between rounded-md p-3 border ${strength ? 'bg-success/5 border-success/20' : 'bg-warning/5 border-warning/20'}`}>
        <span className="flex gap-2 text-sm">{strength ? <CheckCircle2 className="h-4 w-4 text-success shrink-0" /> : <span>{index + 1}.</span>}{item}</span>
        {!isViewMode && <button onClick={() => onChange(items.filter((_, i) => i !== index))}
          aria-label={strength ? 'Eliminar fortaleza' : 'Eliminar recomendación'}><X className="h-4 w-4" /></button>}
      </li>)}</ul> : <p className="text-sm text-muted-foreground text-center py-4">No hay {label.toLowerCase()} registradas.</p>}
    </AccordionContent>
  </AccordionItem>;
}
