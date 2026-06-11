import { useState } from 'react';
import { Send, AlertCircle, Pencil } from 'lucide-react';
import { SubirMoodleModal } from '@/features/entregas/components/SubirMoodleModal';
import { ResponsiveTable, type TableColumn } from '@/shared/components/ui';
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

/** Chip de error: visible (no en title=) para que se lea también en touch. */
function ErrorChip({ mensaje }: { mensaje: string | null }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[11px] text-destructive">
      <AlertCircle className="h-3 w-3 shrink-0" />
      {mensaje ?? 'Falló el último intento'}
    </span>
  );
}

/** Chip "requiere comentario": visible (no en title=) para touch. */
function ComentarioChip() {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-warning">
      <Pencil className="h-3 w-3 shrink-0" />
      requiere comentario
    </span>
  );
}

export function PorEntregarTable({ items }: PorEntregarTableProps) {
  const grupos = agruparPorMateria(items);
  // Modal de subida a Moodle: una sola fuente de verdad a nivel componente,
  // montada fuera de la tabla/cards (antes vivía en un <tr><td colSpan>).
  const [activo, setActivo] = useState<CorreccionPorEntrega | null>(null);

  const columns: TableColumn<CorreccionPorEntrega>[] = [
    {
      key: 'alumno',
      header: 'Alumno',
      render: (item) => (
        <div className="flex flex-col gap-1">
          <span className="font-medium text-foreground">{item.alumno_nombre}</span>
          {item.estado_ultimo_intento === 'error' && (
            <ErrorChip mensaje={item.mensaje_error} />
          )}
        </div>
      ),
    },
    {
      key: 'comision',
      header: 'Comisión',
      render: (item) => (
        <span className="text-muted-foreground">{item.comision_nombre}</span>
      ),
    },
    {
      key: 'trabajo',
      header: 'Trabajo',
      render: (item) => (
        <span className="text-muted-foreground">{item.rubrica_titulo}</span>
      ),
    },
    {
      key: 'nota',
      header: 'Nota',
      render: (item) => (
        <div className="flex flex-col gap-1">
          <span className="font-semibold text-foreground">{item.etiqueta_nota}</span>
          {item.requiere_comentario_tutor && <ComentarioChip />}
        </div>
      ),
    },
    {
      key: 'accion',
      header: 'Acción',
      sticky: true,
      className: 'text-right',
      render: (item) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setActivo(item);
          }}
          className="inline-flex cursor-pointer items-center justify-center gap-1 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-foreground transition-colors hover:bg-accent/80 touch-manipulation min-h-[44px] sm:min-h-0"
        >
          <Send className="h-3 w-3" />
          Subir
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {grupos.map((grupo) => (
        <div key={grupo.nombre} className="overflow-hidden rounded-lg border border-border">
          <div className="bg-muted/40 px-4 py-2 text-sm font-semibold text-foreground">
            {grupo.nombre}
          </div>
          <div className="p-3 lg:p-0">
            <ResponsiveTable
              columns={columns}
              data={grupo.items}
              keyExtractor={(item) => item.correccion_id}
              renderCard={(item) => (
                <PorEntregarCard item={item} onSubir={() => setActivo(item)} />
              )}
            />
          </div>
        </div>
      ))}

      {activo && (
        <SubirMoodleModal
          entregaId={activo.entrega_id}
          alumno={activo.alumno_nombre}
          isOpen={!!activo}
          onClose={() => setActivo(null)}
        />
      )}
    </div>
  );
}

/** Tarjeta mobile de una corrección por entregar. */
function PorEntregarCard({
  item,
  onSubir,
}: {
  item: CorreccionPorEntrega;
  onSubir: () => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <span className="font-medium text-foreground">{item.alumno_nombre}</span>
        <span className="text-xs text-muted-foreground">
          {item.comision_nombre} · {item.rubrica_titulo}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-muted px-2 py-0.5 text-sm font-semibold text-foreground">
          {item.etiqueta_nota}
        </span>
        {item.requiere_comentario_tutor && <ComentarioChip />}
        {item.estado_ultimo_intento === 'error' && (
          <ErrorChip mensaje={item.mensaje_error} />
        )}
      </div>

      <button
        onClick={onSubir}
        className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent/80 touch-manipulation min-h-[44px]"
      >
        <Send className="h-4 w-4" />
        Subir
      </button>
    </div>
  );
}
