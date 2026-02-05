import { Cpu, Package, Pencil, Trash2 } from 'lucide-react';
import { Product } from '../../types/models';

export function ProductCard({
  product,
  canManage,
  onEdit,
  onDelete,
  onSelect,
}: {
  product: Product;
  canManage: boolean;
  onEdit: (p: Product) => void;
  onDelete: (id: string) => void;
  onSelect: (p: Product) => void;
}) {
  const chipsets = product.chipsets || [];

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-xl border border-border bg-surface-1 transition-shadow hover:shadow-card cursor-pointer"
      onClick={() => onSelect(product)}
    >
      {/* Hero */}
      <div className="flex h-36 flex-col items-center justify-center gap-2 bg-surface-2">
        <Package size={36} strokeWidth={1} className="text-text-tertiary opacity-40" />
        {chipsets.length > 0 && (
          <div className="flex flex-wrap justify-center gap-1.5">
            {chipsets.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2 py-0.5 text-2xs font-medium text-accent"
              >
                <Cpu size={10} />
                {c}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col p-3.5">
        <div className="mb-1 flex items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-text-primary">
            {product.name}
          </h3>
          <span
            className={[
              'inline-flex items-center rounded-full px-1.5 py-0.5 text-2xs font-medium',
              product.active
                ? 'bg-success-muted text-success'
                : 'bg-surface-2 text-text-tertiary',
            ].join(' ')}
          >
            {product.active ? 'Active' : 'Inactive'}
          </span>
        </div>
        {product.description && (
          <p className="mb-2 text-2xs text-text-tertiary line-clamp-2">
            {product.description}
          </p>
        )}

        <div className="mt-auto flex gap-3 text-2xs text-text-tertiary">
          <span>{product.boardRevisionCount ?? 0} board rev{(product.boardRevisionCount ?? 0) !== 1 ? 's' : ''}</span>
          <span>{product.firmwareAppCount ?? 0} fw app{(product.firmwareAppCount ?? 0) !== 1 ? 's' : ''}</span>
          <span>{product.firmwareBuildCount ?? 0} build{(product.firmwareBuildCount ?? 0) !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {/* Edit/delete */}
      {canManage && (
        <div
          className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => onEdit(product)}
            className="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
            title="Edit"
            aria-label="Edit"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(product.id)}
            className="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
            title="Delete"
            aria-label="Delete"
          >
            <Trash2 size={13} />
          </button>
        </div>
      )}
    </div>
  );
}
