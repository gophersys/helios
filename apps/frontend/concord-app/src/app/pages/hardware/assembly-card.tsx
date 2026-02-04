import { useEffect, useState } from 'react';
import { Boxes, Pencil, Trash2, ChevronDown } from 'lucide-react';
import { StatusBadge } from '../../components/ui/status-badge';

interface BomItem {
  id: string;
  hardwareRevisionId: string;
  quantity: number;
  hardwareRevision?: {
    id: string;
    version: string;
    status: string;
    component?: {
      id: string;
      name: string;
      category: string;
    };
  };
}

interface AssemblyRevision {
  id: string;
  version: string;
  status: string;
  releaseNotes: string | null;
  bom?: BomItem[];
}

interface Assembly {
  id: string;
  name: string;
  description: string | null;
  imageUrl: string | null;
  revisionCount: number;
  revisions?: AssemblyRevision[];
}

export function AssemblyCard({
  assembly,
  canManage,
  onEdit,
  onDelete,
  onSelect,
}: {
  assembly: Assembly;
  canManage: boolean;
  onEdit: (a: Assembly) => void;
  onDelete: (id: string) => void;
  onSelect: (a: Assembly) => void;
}) {
  const [revDropdown, setRevDropdown] = useState(false);
  const revisions = assembly.revisions || [];
  const [selectedRev, setSelectedRev] = useState<AssemblyRevision | null>(
    revisions[0] || null
  );

  useEffect(() => {
    setSelectedRev((assembly.revisions || [])[0] || null);
  }, [assembly.revisions]);

  const currentBom = selectedRev?.bom || [];

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-xl border border-border bg-surface-1 transition-shadow hover:shadow-card cursor-pointer"
      onClick={() => onSelect(assembly)}
    >
      {/* Hero image */}
      <div className="flex h-36 items-center justify-center bg-surface-2">
        {assembly.imageUrl ? (
          <img
            src={assembly.imageUrl}
            alt={assembly.name}
            className="h-full w-full object-contain p-3"
          />
        ) : (
          <Boxes size={36} strokeWidth={1} className="text-text-tertiary opacity-40" />
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col p-3.5">
        <h3 className="mb-1 truncate text-sm font-semibold text-text-primary">
          {assembly.name}
        </h3>
        {assembly.description && (
          <div className="mb-2 text-2xs text-text-tertiary line-clamp-2">
            {assembly.description}
          </div>
        )}

        {/* Revision selector */}
        {revisions.length > 0 && (
          <div className="relative" onClick={(e) => e.stopPropagation()}>
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
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {revisions.length === 0 && (
          <div className="text-2xs text-text-tertiary">No revisions</div>
        )}

        {/* BOM list */}
        {currentBom.length > 0 && (
          <div className="mt-2 space-y-0.5">
            {currentBom.map((item) => (
              <div
                key={item.id}
                className="text-2xs text-text-secondary"
              >
                {item.quantity}x{' '}
                {item.hardwareRevision?.component?.name || 'Unknown'}{' '}
                <span className="text-text-tertiary">
                  ({item.hardwareRevision?.version || '?'})
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit/delete */}
      {canManage && (
        <div
          className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => onEdit(assembly)}
            className="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
            title="Edit"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(assembly.id)}
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
