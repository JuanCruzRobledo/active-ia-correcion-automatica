/**
 * CorrectionsProgress - Coordinador corrections progress section.
 *
 * Displays progress bars for each comisión showing correction status.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Coordinador
 */

import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';
import { Progress } from '@/shared/components/ui/Progress';

interface ProgressItem {
  id: number;
  comision: string;
  tutor: string;
  completed: number;
  total: number;
  lastActivity: string; // ISO 8601
}

interface CorrectionsProgressProps {
  progress: ProgressItem[];
}

export function CorrectionsProgress({ progress }: CorrectionsProgressProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h2 className="mb-4 text-lg font-semibold text-foreground">
        Estado de Correcciones por Comisión
      </h2>
      <div className="space-y-6">
        {progress.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No hay comisiones con correcciones en progreso
          </p>
        ) : (
          progress.map((item) => {
            const percentage = Math.round((item.completed / item.total) * 100);
            const isCompleted = item.completed === item.total;

            return (
              <div key={item.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {item.comision} ({item.tutor})
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {isCompleted ? (
                        <>
                          Completado:{' '}
                          {formatDistanceToNow(new Date(item.lastActivity), {
                            addSuffix: true,
                            locale: es,
                          })}
                        </>
                      ) : (
                        <>
                          Última actividad:{' '}
                          {formatDistanceToNow(new Date(item.lastActivity), {
                            addSuffix: true,
                            locale: es,
                          })}
                        </>
                      )}
                    </p>
                  </div>
                  <span className="text-sm font-medium text-foreground">
                    {item.completed}/{item.total} ({percentage}%)
                  </span>
                </div>
                <Progress value={percentage} className="h-2" />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
