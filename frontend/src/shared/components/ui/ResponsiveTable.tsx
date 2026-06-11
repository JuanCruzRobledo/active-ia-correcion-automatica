// shared/components/ui/ResponsiveTable.tsx
/**
 * Tabla responsive: en desktop (lg:) renderiza la <table> clasica reusando
 * el componente Table; en mobile (<lg) renderiza una card-list apilada.
 *
 * Reusa el tipo TableColumn<T> de Table.tsx, asi la fuente de columnas es unica.
 * Backward-compatible: Table.tsx sigue intacto para uso desktop directo.
 *
 * Ref: PLAN_MOBILE_PWA.md §6.1
 */

import { type ReactNode } from 'react';
import { cn } from '@/shared/utils/cn';
import { Table, type TableColumn } from './Table';

export interface ResponsiveTableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  keyExtractor: (item: T) => string | number;
  /** Click sobre fila (desktop) o sobre tarjeta (mobile). */
  onRowClick?: (item: T) => void;
  /** Escape hatch: render custom de la tarjeta mobile. */
  renderCard?: (item: T) => ReactNode;
  /** Contenido a mostrar cuando data esta vacia (desktop y mobile). */
  emptyState?: ReactNode;
  /** Mensaje de vacio simple (fallback si no se pasa emptyState). */
  emptyMessage?: string;
  /** Clase para el wrapper de la <table> desktop. */
  className?: string;
  /** Clase para el contenedor de la card-list mobile. */
  cardClassName?: string;
}

/**
 * Tarjeta fallback: apila las columnas como pares "header : valor".
 * Las columnas sticky (acciones ancladas a la derecha) no tienen sentido en
 * formato card, asi que se omiten del listado label/valor pero se renderizan
 * al pie de la tarjeta como bloque de acciones.
 */
const DefaultCard = <T,>({
  item,
  columns,
}: {
  item: T;
  columns: TableColumn<T>[];
}) => {
  const labelColumns = columns.filter((column) => !column.sticky);
  const actionColumns = columns.filter((column) => column.sticky);

  const renderValue = (column: TableColumn<T>): ReactNode =>
    column.render
      ? column.render(item)
      : String((item as Record<string, unknown>)[column.key] ?? '');

  return (
    <>
      <dl className="flex flex-col">
        {labelColumns.map((column) => (
          <div
            key={column.key}
            className="flex justify-between gap-3 py-1.5 border-b border-border/50 last:border-0"
          >
            <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider shrink-0">
              {column.header}
            </dt>
            <dd className="text-sm text-foreground text-right min-w-0 break-words">
              {renderValue(column)}
            </dd>
          </div>
        ))}
      </dl>
      {actionColumns.length > 0 && (
        <div className="flex items-center justify-end gap-2 pt-3 mt-1 border-t border-border/50">
          {actionColumns.map((column) => (
            <div key={column.key}>{renderValue(column)}</div>
          ))}
        </div>
      )}
    </>
  );
};

export const ResponsiveTable = <T,>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  renderCard,
  emptyState,
  emptyMessage = 'No hay datos para mostrar',
  className,
  cardClassName,
}: ResponsiveTableProps<T>) => {
  if (data.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        {emptyState ?? emptyMessage}
      </div>
    );
  }

  return (
    <>
      {/* Desktop: tabla clasica intacta (reusa Table, mismo look). */}
      <div className="hidden lg:block">
        <Table
          columns={columns}
          data={data}
          keyExtractor={keyExtractor}
          onRowClick={onRowClick}
          emptyMessage={emptyMessage}
          className={className}
        />
      </div>

      {/* Mobile: card-list apilada. */}
      <div className={cn('lg:hidden flex flex-col gap-3', cardClassName)}>
        {data.map((item) => (
          <div
            key={keyExtractor(item)}
            onClick={() => onRowClick?.(item)}
            className={cn(
              'rounded-lg border border-border bg-card p-4 transition-colors',
              onRowClick &&
                'min-h-[44px] cursor-pointer hover:bg-muted/50 touch-manipulation'
            )}
          >
            {renderCard ? (
              renderCard(item)
            ) : (
              <DefaultCard item={item} columns={columns} />
            )}
          </div>
        ))}
      </div>
    </>
  );
};
