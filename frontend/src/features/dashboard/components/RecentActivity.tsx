/**
 * RecentActivity - Admin recent activity section.
 *
 * Displays a list of recent system activities/events.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Admin
 * Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
 */

import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';
import { Spinner } from '@/shared/components/ui';

interface Activity {
  id: number;
  text: string;
  timestamp: string; // ISO 8601
}

interface RecentActivityProps {
  activities: Activity[];
  isLoading?: boolean;
}

export function RecentActivity({ activities, isLoading = false }: RecentActivityProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
      <h3 className="mb-4 text-lg font-semibold text-foreground">Actividad Reciente</h3>
      <div className="space-y-4">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Spinner size="default" />
          </div>
        ) : activities.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No hay actividades registradas
          </p>
        ) : (
          activities.map((activity) => (
            <div key={activity.id} className="flex items-start gap-3">
              <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-foreground line-clamp-3 break-words">{activity.text}</p>
                <p className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(activity.timestamp), {
                    addSuffix: true,
                    locale: es,
                  })}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
