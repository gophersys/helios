import { type KeyboardEvent, type ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
  className?: string;
}

interface ResourceTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (item: T, index: number) => string;
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
}

export function ResourceTable<T>({
  columns,
  data,
  keyFn,
  onRowClick,
  emptyMessage = 'No resources found',
}: ResourceTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-text-tertiary">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary ${col.className || ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {data.map((item, idx) => (
            <tr
              key={keyFn(item, idx)}
              className={`bg-surface-1 transition-colors ${
                onRowClick ? 'cursor-pointer hover:bg-surface-2' : ''
              }`}
              onClick={() => onRowClick?.(item)}
              {...(onRowClick ? { tabIndex: 0, onKeyDown: (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(item); } } } : {})}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-3 py-2 ${col.className || ''}`}>
                  {col.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
