interface DirectoriosPermitidosEditorProps {
  metadata: Record<string, unknown>;
  onChange: (metadata: Record<string, unknown>) => void;
}

const DIRECTORIOS = ['node_modules', 'dist', 'target', 'build', 'out', 'bin'];

function objeto(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

/** Excepciones explícitas de la consigna, conservando el resto de la metadata. */
export function DirectoriosPermitidosEditor({ metadata, onChange }: DirectoriosPermitidosEditorProps) {
  const politica = objeto(metadata.politica_entrega);
  const permitidos = Array.isArray(politica.directorios_permitidos)
    ? politica.directorios_permitidos.filter((value): value is string => typeof value === 'string')
    : [];

  const cambiar = (directorio: string, permitido: boolean) => {
    const directorios = permitido
      ? [...new Set([...permitidos, directorio])]
      : permitidos.filter((value) => value !== directorio);
    onChange({ ...metadata, politica_entrega: { ...politica, directorios_permitidos: directorios } });
  };

  return (
    <fieldset className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
      <legend className="px-1 text-sm font-medium text-foreground">Directorios solicitados por la consigna</legend>
      <p className="text-xs text-muted-foreground">
        Marcá una excepción solo si la consigna solicita ese directorio. Sus archivos podrán incluirse
        según las extensiones de la rúbrica y no activarán el tope de 50/100.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {DIRECTORIOS.map((directorio) => (
          <label key={directorio} className="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={permitidos.includes(directorio)}
              onChange={(event) => cambiar(directorio, event.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            <span className="break-all font-mono text-xs">{directorio}/</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
