/**
 * QuickActions - Admin quick actions section.
 *
 * Displays a card with action buttons for common admin tasks.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Admin
 */

import type { LucideIcon } from 'lucide-react';
import { Button } from '@/shared/components/ui/Button';

interface Action {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
}

interface QuickActionsProps {
  actions: Action[];
}

export function QuickActions({ actions }: QuickActionsProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h3 className="mb-4 text-lg font-semibold text-foreground">Acciones Rápidas</h3>
      <div className="space-y-3">
        {actions.map((action, index) => {
          const Icon = action.icon;
          return (
            <Button
              key={index}
              variant="outline"
              className="w-full justify-start"
              onClick={action.onClick}
            >
              <Icon className="mr-2 h-4 w-4" />
              {action.label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
