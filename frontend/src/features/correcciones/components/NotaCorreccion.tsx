import { Calculator } from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { cn } from '../../../shared/utils/cn';
import type { Correccion } from '../types';
import { LimiteNotaEntrega } from '../../entregas/components/LimiteNotaEntrega';
interface NotaCorreccionProps {
  correccion: Correccion;
  nota: number;
  isViewMode: boolean;
  setNota: (nota: number) => void;
  handleRecalcularNota: () => void;
}
const getNotaColor = (nota: number) => nota >= 80 ? 'text-success' : nota >= 60 ? 'text-warning' : 'text-destructive';
export function NotaCorreccion({ correccion, nota, isViewMode, setNota, handleRecalcularNota }: NotaCorreccionProps) {
  return <>
        {/* 1. NOTA FINAL - Compact and prominent */}
        <section className="bg-gradient-to-br from-muted/80 to-muted/40 rounded-lg p-4 border border-border">
          <div className="flex items-center justify-between gap-4">
            {/* Left: Label and Recalcular button */}
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide">
                {isViewMode ? 'Nota Final' : 'Nota académica'}
              </h3>
              {!isViewMode && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRecalcularNota}
                  className="gap-1.5 text-xs"
                >
                  <Calculator className="h-3.5 w-3.5" />
                  Recalcular
                </Button>
              )}
            </div>

            {/* Right: Nota display */}
            <div className="flex items-baseline gap-2">
              {isViewMode ? (
                <div className={cn('text-4xl font-bold', getNotaColor(Number(correccion.nota)))}>
                  {Number(correccion.nota).toFixed(1)}
                </div>
              ) : (
                <input
                  aria-label="Nota académica"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={nota}
                  onChange={(e) => setNota(Number(e.target.value))}
                  className={cn(
                    'text-4xl font-bold text-center w-28 bg-transparent',
                    'border-b-2 border-border focus:border-accent focus:outline-none',
                    'transition-colors',
                    getNotaColor(nota)
                  )}
                />
              )}
              <span className="text-sm text-muted-foreground">/ 100</span>
            </div>
          </div>

          {/* Merit score (nota_antes_penalizaciones) */}
          {correccion.nota_antes_penalizaciones != null &&
            correccion.nota_antes_penalizaciones !== Number(correccion.nota) && (
            <div className="mt-3 pt-3 border-t border-border/50 text-sm text-muted-foreground">
              Puntaje por mérito: <span className="font-medium text-foreground">{Number(correccion.nota_antes_penalizaciones).toFixed(1)}</span> / 100
            </div>
          )}
        </section>

        {isViewMode && correccion.nota_academica != null && correccion.limite_nota != null && (
          <p className="text-sm text-muted-foreground">
            Nota académica: <span className="font-medium text-foreground">{Number(correccion.nota_academica).toFixed(1)}</span> / 100
          </p>
        )}
        <LimiteNotaEntrega limiteNota={correccion.limite_nota} rutas={correccion.rutas_penalizables} />

  </>;
}
