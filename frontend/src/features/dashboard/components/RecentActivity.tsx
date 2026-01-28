/**
 * RecentActivity - Admin recent activity section.
 *
 * Displays a list of recent system activities/events.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Admin
 */

import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';

interface Activity {
  id: number;
  text: string;
  timestamp: string; // ISO 8601
}

interface RecentActivityProps {
  activities: Activity[];
}

export function RecentActivity({ activities }: RecentActivityProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h3 className="mb-4 text-lg font-semibold text-foreground">Actividad Reciente</h3>
      <div className="space-y-4">
        {activities.length === 0 ? (
          <p className="text-sm text-muted-foreground">No hay actividad reciente</p>
        ) : (
          activities.map((activity) => (
            <div key={activity.id} className="flex items-start gap-3">
              <div className="mt-1 h-2 w-2 rounded-full bg-accent" />
              <div className="flex-1">
                <p className="text-sm text-foreground">{activity.text}</p>
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
