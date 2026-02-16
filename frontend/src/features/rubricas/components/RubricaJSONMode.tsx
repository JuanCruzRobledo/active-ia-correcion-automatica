import { useState } from 'react';
import { Upload, Copy, Check } from 'lucide-react';
import { JSON_EXAMPLE } from '../constants/rubrica-constants';

interface Props {
  jsonText: string;
  setJsonText: (text: string) => void;
  jsonError: string | null;
  setJsonError: (error: string | null) => void;
  currentJSON?: string; // JSON actual para copiar (en modo edición)
}

export function RubricaJSONMode({ jsonText, setJsonText, jsonError, setJsonError, currentJSON }: Props) {
  const [copied, setCopied] = useState(false);

  const handleJSONFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      setJsonText(event.target?.result as string);
      setJsonError(null);
    };
    reader.readAsText(file);
  };

  const handleCopyExample = async () => {
    try {
      // Si hay currentJSON, copiar eso; sino copiar el ejemplo
      const textToCopy = currentJSON || JSON_EXAMPLE;
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Error copiando al portapapeles:', err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Cargar desde JSON</h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopyExample}
            className="flex items-center gap-1.5 px-2 py-1 text-xs text-muted-foreground hover:text-foreground border border-border rounded hover:bg-muted transition-colors"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-success" />
                <span>Copiado</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                <span>{currentJSON ? 'Copiar JSON actual' : 'Copiar ejemplo'}</span>
              </>
            )}
          </button>
          <label className="flex items-center gap-1.5 px-2 py-1 text-xs text-accent cursor-pointer hover:underline border border-border rounded hover:bg-muted transition-colors">
            <Upload className="h-3 w-3" />
            Subir .json
            <input
              type="file"
              accept=".json"
              className="sr-only"
              onChange={handleJSONFileUpload}
            />
          </label>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Pega o sube un JSON con la estructura completa de la rúbrica. Se cargará en el editor para revisión.
      </p>

      <textarea
        value={jsonText}
        onChange={(e) => {
          setJsonText(e.target.value);
          setJsonError(null);
        }}
        className="w-full h-96 px-3 py-2 border border-input rounded-md bg-background text-foreground text-xs font-mono focus:outline-none focus:ring-2 focus:ring-ring resize-none"
        placeholder={JSON_EXAMPLE}
      />
      {jsonError && <p className="text-sm text-destructive">{jsonError}</p>}
    </div>
  );
}
