import { useState } from 'react';
import { Send, AlertCircle, Pencil } from 'lucide-react';
import { SubirMoodleModal } from '@/features/entregas/components/SubirMoodleModal';
import type { CorreccionPorEntrega } from '../types';

interface PorEntregarTableProps {
  items: CorreccionPorEntrega[];
}

/** Agrupa las correcciones por materia para una lectura más clara. */
function agruparPorMateria(items: CorreccionPorEntrega[]) {
  const grupos = new Map<number, { nombre: string; items: CorreccionPorEntrega[] }>();
  for (const item of items) {
    const g = grupos.get(item.materia_id);
    if (g) g.items.push(item);
    else grupos.set(item.materia_id, { nombre: item.materia_nombre, items: [item] });
  }
  return Array.from(grupos.values());
}

export function PorEntregarTable({ items }: PorEntregarTableProps) {
  const grupos = agruparPorMateria(items);

  return (
    <div className="space-y-6">
      {grupos.map((grupo) => (
        <div key={grupo.nombre} className="overflow-hidden rounded-lg border border-border">
          <div className="bg-muted/40 px-4 py-2 text-sm font-semibold text-foreground">
            {grupo.nombre}
          </div>
          <table className="w-full text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Alumno</th>
                <th className="px-4 py-2 text-left font-medium">Comisión</th>
                <th className="px-4 py-2 text-left font-medium">Trabajo</th>
                <th className="px-4 py-2 text-left font-medium">Nota</th>
                <th className="px-4 py-2 text-right font-medium">Acción</th>
              </tr>
            </thead>
            <tbody>
              {grupo.items.map((item) => (
                <PorEntregarRow key={item.correccion_id} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function PorEntregarRow({ item }: { item: CorreccionPorEntrega }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <tr className="border-b border-border last:border-0 hover:bg-muted/20">
        <td className="px-4 py-2 font-medium text-foreground">
          {item.alumno_nombre}
          {item.estado_ultimo_intento === 'error' && (
            <span
              className="ml-2 inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[11px] text-destructive"
              title={item.mensaje_error ?? 'Falló el último intento'}
            >
              <AlertCircle className="h-3 w-3" />
              Falló el último intento
            </span>
          )}
        </td>
        <td className="px-4 py-2 text-muted-foreground">{item.comision_nombre}</td>
        <td className="px-4 py-2 text-muted-foreground">{item.rubrica_titulo}</td>
        <td className="px-4 py-2">
          <span className="font-semibold text-foreground">{item.etiqueta_nota}</span>
          {item.requiere_comentario_tutor && (
            <span
              className="ml-2 inline-flex items-center gap-1 text-[11px] text-warning"
              title="Requiere que escribas un comentario antes de enviar"
            >
              <Pencil className="h-3 w-3" />
              requiere comentario
            </span>
          )}
        </td>
        <td className="px-4 py-2 text-right">
          <button
            onClick={() => setOpen(true)}
            className="inline-flex cursor-pointer items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-foreground transition-colors hover:bg-accent/80"
          >
            <Send className="h-3 w-3" />
            Subir
          </button>
        </td>
      </tr>

      {open && (
        <tr>
          <td colSpan={5} className="p-0">
            <SubirMoodleModal
              entregaId={item.entrega_id}
              alumno={item.alumno_nombre}
              isOpen={open}
              onClose={() => setOpen(false)}
            />
          </td>
        </tr>
      )}
    </>
  );
}
