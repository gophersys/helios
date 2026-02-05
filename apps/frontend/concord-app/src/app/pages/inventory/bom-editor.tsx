import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { InventoryRevisionOption } from '../../types/models';

interface BomEntry {
  inventoryRevisionId: string;
  quantity: number;
}

interface BomEditorProps {
  bom: BomEntry[];
  onChange: (bom: BomEntry[]) => void;
  availableRevisions: InventoryRevisionOption[];
}

const CATEGORY_LABELS: Record<string, string> = {
  SOM: 'SoM',
  CARRIER_BOARD: 'Carrier Board',
  ACCESSORY: 'Accessory',
};

export function BomEditor({ bom, onChange, availableRevisions }: BomEditorProps) {
  const [searchTerm, setSearchTerm] = useState('');

  // Group revisions by component for display
  const grouped = availableRevisions.reduce(
    (acc, rev) => {
      const key = rev.componentId;
      if (!acc[key]) {
        acc[key] = {
          componentName: rev.componentName,
          category: rev.category,
          revisions: [],
        };
      }
      acc[key].revisions.push(rev);
      return acc;
    },
    {} as Record<string, { componentName: string; category: string; revisions: InventoryRevisionOption[] }>
  );

  const selectedIds = new Set(bom.map((b) => b.inventoryRevisionId));

  const addItem = (revisionId: string) => {
    if (!selectedIds.has(revisionId)) {
      onChange([...bom, { inventoryRevisionId: revisionId, quantity: 1 }]);
    }
  };

  const removeItem = (revisionId: string) => {
    onChange(bom.filter((b) => b.inventoryRevisionId !== revisionId));
  };

  const updateQuantity = (revisionId: string, quantity: number) => {
    onChange(
      bom.map((b) =>
        b.inventoryRevisionId === revisionId ? { ...b, quantity: Math.max(1, quantity) } : b
      )
    );
  };

  const getRevisionLabel = (revisionId: string) => {
    const rev = availableRevisions.find((r) => r.id === revisionId);
    return rev ? `${rev.componentName} (${rev.version})` : revisionId;
  };

  const filteredGroups = Object.entries(grouped).filter(([, group]) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      group.componentName.toLowerCase().includes(term) ||
      group.category.toLowerCase().includes(term) ||
      group.revisions.some((r) => r.version.toLowerCase().includes(term))
    );
  });

  return (
    <div>
      <label className="mb-1.5 block text-2xs font-medium text-text-tertiary">
        Bill of Materials
      </label>

      {/* Current BOM items */}
      {bom.length > 0 && (
        <div className="mb-3 space-y-1.5">
          {bom.map((item) => (
            <div
              key={item.inventoryRevisionId}
              className="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-3 py-2"
            >
              <span className="flex-1 text-xs text-text-primary">
                {getRevisionLabel(item.inventoryRevisionId)}
              </span>
              <input
                type="number"
                min={1}
                value={item.quantity}
                onChange={(e) =>
                  updateQuantity(item.inventoryRevisionId, parseInt(e.target.value) || 1)
                }
                className="w-16 rounded border border-border bg-surface-1 px-2 py-1 text-center text-xs text-text-primary focus:border-accent focus:outline-none"
              />
              <button
                type="button"
                onClick={() => removeItem(item.inventoryRevisionId)}
                className="rounded p-1 text-text-tertiary hover:text-error"
                title="Remove"
                aria-label="Remove"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add component search */}
      <div className="rounded-lg border border-border bg-surface-0">
        <div className="p-2">
          <input
            type="text"
            placeholder="Search components..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded border border-border bg-surface-1 px-2.5 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </div>
        <div className="max-h-48 overflow-y-auto border-t border-border">
          {filteredGroups.length === 0 ? (
            <div className="px-3 py-4 text-center text-2xs text-text-tertiary">
              No components found
            </div>
          ) : (
            filteredGroups.map(([compId, group]) => (
              <div key={compId}>
                <div className="sticky top-0 bg-surface-2 px-3 py-1.5 text-2xs font-semibold text-text-secondary">
                  {group.componentName}
                  <span className="ml-1.5 font-normal text-text-tertiary">
                    {CATEGORY_LABELS[group.category] || group.category}
                  </span>
                </div>
                {group.revisions.map((rev) => {
                  const isSelected = selectedIds.has(rev.id);
                  return (
                    <button
                      key={rev.id}
                      type="button"
                      disabled={isSelected}
                      onClick={() => addItem(rev.id)}
                      className={[
                        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-2xs',
                        isSelected
                          ? 'bg-accent-muted text-text-tertiary'
                          : 'hover:bg-surface-2 text-text-primary',
                      ].join(' ')}
                    >
                      <Plus size={12} className={isSelected ? 'opacity-30' : 'text-accent'} />
                      <span className="font-medium">{rev.version}</span>
                      <span className="text-text-tertiary">{rev.status}</span>
                      {isSelected && (
                        <span className="ml-auto text-2xs text-accent">Added</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
