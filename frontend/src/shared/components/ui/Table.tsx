// shared/components/ui/Table.tsx
/**
 * Generic table component with sticky actions column
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { type ReactNode } from 'react';
import { cn } from '@/shared/utils/cn';

export interface TableColumn<T> {
  key: string;
  header: string;
  render?: (item: T) => ReactNode;
  className?: string;
  /** If true, makes this column sticky on the right side */
  sticky?: boolean;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  keyExtractor: (item: T) => string | number;
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
  className?: string;
}

export const Table = <T,>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  emptyMessage = 'No hay datos para mostrar',
  className,
}: TableProps<T>) => {
  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-muted">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  'px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider',
                  column.sticky && 'sticky right-0 bg-muted shadow-[-4px_0_4px_rgba(0,0,0,0.05)]',
                  column.className
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-card divide-y divide-border">
          {data.map((item) => (
            <tr
              key={keyExtractor(item)}
              onClick={() => onRowClick?.(item)}
              className={cn(
                'hover:bg-muted/50 transition-colors',
                onRowClick && 'cursor-pointer'
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    'px-6 py-4 whitespace-nowrap text-sm text-foreground',
                    column.sticky && 'sticky right-0 bg-card shadow-[-4px_0_4px_rgba(0,0,0,0.05)]',
                    column.className
                  )}
                >
                  {column.render
                    ? column.render(item)
                    : String((item as any)[column.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
