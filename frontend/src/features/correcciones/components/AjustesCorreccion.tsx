import { X, XCircle, AlertTriangle } from 'lucide-react';
import type { Correccion } from '../types';
interface AjustesCorreccionProps {
  correccion: Correccion;
  cdAplicada: string | null;
  penalizaciones: string[];
  isViewMode: boolean;
  setCdAplicada: (id: string | null) => void;
  setPenalizaciones: (ids: string[]) => void;
  handleRecalcularNota: () => void;
}
export function AjustesCorreccion({ correccion, cdAplicada, penalizaciones, isViewMode, setCdAplicada, setPenalizaciones, handleRecalcularNota }: AjustesCorreccionProps) {
  return <>
        {/* Condición de desaprobación alert */}
        {cdAplicada && (
          <section className="rounded-lg border-2 border-destructive/50 bg-destructive/10 p-4">
            <div className="flex items-start gap-3">
              <XCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-destructive text-sm">
                    Nota limitada por incumplimiento de requisitos
                  </h4>
                  {!isViewMode && (
                    <button
                      onClick={() => {
                        setCdAplicada(null);
                        handleRecalcularNota();
                      }}
                      className="text-destructive hover:text-destructive/70 transition-colors"
                      title="Quitar condición de desaprobación"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <ul className="text-sm text-foreground mt-2 space-y-1">
                  <li className="flex items-start gap-2">
                    <span className="text-destructive mt-1">•</span>
                    <span>{correccion.condicion_desaprobacion_descripcion || cdAplicada}</span>
                  </li>
                </ul>
                {isViewMode && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Esto limita la nota máxima alcanzable a{' '}
                    <span className="font-medium">{Number(correccion.nota).toFixed(1)}</span>.
                    {correccion.nota_antes_penalizaciones != null && (
                      <> Tu puntaje obtenido por mérito fue{' '}
                      <span className="font-medium">{Number(correccion.nota_antes_penalizaciones).toFixed(1)}</span>/100.</>
                    )}
                  </p>
                )}
              </div>
            </div>
          </section>
        )}

        {/* Penalizaciones alert */}
        {penalizaciones && penalizaciones.length > 0 && (
          <section className="rounded-lg border-2 border-warning/50 bg-warning/10 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h4 className="font-semibold text-warning text-sm">
                  Penalizaciones aplicadas
                </h4>
                <ul className="text-sm text-foreground mt-2 space-y-1">
                  {penalizaciones.map((penId) => {
                    const penInfo = correccion.penalizaciones_descripciones?.find(p => p.id === penId);
                    return (
                      <li key={penId} className="flex items-center justify-between gap-2">
                        <div className="flex items-start gap-2 flex-1">
                          <span className="text-warning mt-1">•</span>
                          <span>
                            {penInfo?.descripcion || penId}
                            {penInfo && penInfo.descuento_porcentaje > 0 && (
                              <span className="text-muted-foreground"> (descuento del {penInfo.descuento_porcentaje}%)</span>
                            )}
                          </span>
                        </div>
                        {!isViewMode && (
                          <button
                            onClick={() => setPenalizaciones(penalizaciones.filter(id => id !== penId))}
                            className="text-warning hover:text-warning/70 transition-colors flex-shrink-0"
                            title="Quitar penalización"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {isViewMode && correccion.nota_antes_penalizaciones != null && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Puntaje antes de penalizaciones:{' '}
                    <span className="font-medium">{Number(correccion.nota_antes_penalizaciones).toFixed(1)}</span>/100
                    {' → '}Nota final: <span className="font-medium">{Number(correccion.nota).toFixed(1)}</span>/100
                  </p>
                )}
              </div>
            </div>
          </section>
        )}

  </>;
}
