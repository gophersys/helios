import { useEffect, useState } from 'react';
import { Cpu, Pencil, Trash2, ChevronDown } from 'lucide-react';
import { StatusBadge } from '../../components/ui/status-badge';

interface Revision {
  id: string;
  version: string;
  status: string;
  releaseNotes: string | null;
}

interface Component {
  id: string;
  name: string;
  description: string | null;
  category: string;
  manufacturer: string;
  partNumber: string;
  imageUrl: string | null;
  revisionCount: number;
  revisions?: Revision[];
}

const CATEGORY_LABELS: Record<string, string> = {
  SOM: 'SoM',
  CARRIER_BOARD: 'Carrier Board',
  ACCESSORY: 'Accessory',
};

export function ComponentCard({
  component,
  canManage,
  onEdit,
  onDelete,
  onSelect,
}: {
  component: Component;
  canManage: boolean;
  onEdit: (c: Component) => void;
  onDelete: (id: string) => void;
  onSelect: (c: Component) => void;
}) {
  const [revDropdown, setRevDropdown] = useState(false);
  const [selectedRev, setSelectedRev] = useState<Revision | null>(
    component.revisions?.[0] || null
  );

  useEffect(() => {
    setSelectedRev(component.revisions?.[0] || null);
  }, [component.revisions]);

  const revisions = component.revisions || [];

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-xl border border-border bg-surface-1 transition-shadow hover:shadow-card cursor-pointer"
      onClick={() => onSelect(component)}
    >
      {/* Hero image */}
      <div className="flex h-36 items-center justify-center bg-surface-2">
        {component.imageUrl ? (
          <img
            src={component.imageUrl}
            alt={component.name}
            className="h-full w-full object-contain p-3"
          />
        ) : (
          <Cpu size={36} strokeWidth={1} className="text-text-tertiary opacity-40" />
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col p-3.5">
        <div className="mb-1 flex items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-text-primary">
            {component.name}
          </h3>
          <span className="shrink-0 rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
            {CATEGORY_LABELS[component.category] || component.category}
          </span>
        </div>
        <div className="mb-2 text-2xs text-text-tertiary">
          {component.manufacturer} &middot; {component.partNumber}
        </div>

        {/* Revision selector */}
        {revisions.length > 0 && (
          <div className="relative mt-auto" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setRevDropdown(!revDropdown)}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-surface-0 px-2.5 py-1.5 text-2xs text-text-secondary hover:border-text-tertiary"
            >
              <span className="flex items-center gap-1.5">
                <span className="font-medium">{selectedRev?.version || revisions[0].version}</span>
                <StatusBadge status={(selectedRev || revisions[0]).status} />
              </span>
              <ChevronDown size={12} />
            </button>

            {revDropdown && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setRevDropdown(false)}
                />
                <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-48 overflow-y-auto rounded-lg border border-border bg-surface-1 py-1 shadow-card">
                  {revisions.map((rev) => (
                    <button
                      key={rev.id}
                      onClick={() => {
                        setSelectedRev(rev);
                        setRevDropdown(false);
                      }}
                      className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-2xs hover:bg-surface-2"
                    >
                      <span className="font-medium text-text-primary">
                        {rev.version}
                      </span>
                      <StatusBadge status={rev.status} />
                      {rev.releaseNotes && (
                        <span className="ml-auto truncate text-text-tertiary">
                          {rev.releaseNotes}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {revisions.length === 0 && (
          <div className="mt-auto text-2xs text-text-tertiary">No revisions</div>
        )}
      </div>

      {/* Edit/delete */}
      {canManage && (
        <div
          className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => onEdit(component)}
            className="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
            title="Edit"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(component.id)}
            className="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
            title="Delete"
          >
            <Trash2 size={13} />
          </button>
        </div>
      )}
    </div>
  );
}
