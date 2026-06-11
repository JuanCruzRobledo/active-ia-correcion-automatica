import { Upload, FileText, Trash2 } from 'lucide-react';

interface Props {
  pdfFile: File | null;
  setPdfFile: (file: File | null) => void;
  isError: boolean;
}

export function RubricaPDFMode({ pdfFile, setPdfFile, isError }: Props) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Subir PDF de Consigna</h3>
      <p className="text-sm text-muted-foreground">
        La IA extraerá los criterios de evaluación del PDF automáticamente.
      </p>

      {!pdfFile ? (
        <label className="flex flex-col items-center justify-center w-full h-40 px-4 bg-card border-2 border-dashed border-border rounded-lg cursor-pointer hover:bg-muted transition-colors">
          <Upload className="h-8 w-8 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-accent">Haz clic</span> o arrastra un PDF aquí
          </p>
          <p className="text-xs text-muted-foreground mt-1">Solo archivos PDF (máx. 10 MB)</p>
          <input
            type="file"
            accept=".pdf"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) setPdfFile(file);
            }}
          />
        </label>
      ) : (
        <div className="flex items-center justify-between bg-muted rounded-md px-3 py-2.5">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-accent" />
            <span className="text-sm text-foreground">{pdfFile.name}</span>
          </div>
          <button
            type="button"
            onClick={() => setPdfFile(null)}
            className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center text-muted-foreground hover:text-destructive touch-manipulation sm:min-h-0 sm:min-w-0"
            aria-label="Quitar PDF"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {isError && (
        <p className="text-sm text-destructive">
          Error al generar la rúbrica. Verifica tu API Key y vuelve a intentar.
        </p>
      )}
    </div>
  );
}
