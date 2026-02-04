import { GitBranch, Pencil, Trash2, ExternalLink } from 'lucide-react';
import { StatusBadge } from '../../components/ui/status-badge';

interface LatestRelease {
  id: string;
  version: string;
  status: string;
  releasedAt: string | null;
}

interface Codebase {
  id: string;
  name: string;
  description: string | null;
  repoUrl: string | null;
  defaultBranch: string;
  imageKey: string | null;
  imageUrl: string | null;
  releaseCount: number;
  latestRelease: LatestRelease | null;
  createdAt: string;
  updatedAt: string;
}

export function CodebaseCard({
  codebase,
  canManage,
  onEdit,
  onDelete,
  onSelect,
}: {
  codebase: Codebase;
  canManage: boolean;
  onEdit: (c: Codebase) => void;
  onDelete: (id: string) => void;
  onSelect: (c: Codebase) => void;
}) {
  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-xl border border-border bg-surface-1 transition-shadow hover:shadow-card cursor-pointer"
      onClick={() => onSelect(codebase)}
    >
      {/* Hero image */}
      <div className="flex h-36 items-center justify-center bg-surface-2">
        {codebase.imageUrl ? (
          <img
            src={codebase.imageUrl}
            alt={codebase.name}
            className="h-full w-full object-contain p-3"
          />
        ) : (
          <GitBranch size={36} strokeWidth={1} className="text-text-tertiary opacity-40" />
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col p-3.5">
        <div className="mb-1 flex items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-text-primary">
            {codebase.name}
          </h3>
        </div>
        {codebase.description && (
          <p className="mb-2 text-2xs text-text-tertiary line-clamp-2">
            {codebase.description}
          </p>
        )}

        {codebase.repoUrl && (
          <div className="mb-2" onClick={(e) => e.stopPropagation()}>
            <a
              href={codebase.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-2xs text-accent hover:underline"
            >
              <ExternalLink size={11} />
              Repository
            </a>
          </div>
        )}

        {/* Latest release badge */}
        <div className="mt-auto">
          {codebase.latestRelease ? (
            <div className="flex items-center gap-2">
              <span className="text-2xs font-medium text-text-secondary">
                {codebase.latestRelease.version}
              </span>
              <StatusBadge status={codebase.latestRelease.status} />
            </div>
          ) : (
            <div className="text-2xs text-text-tertiary">
              {codebase.releaseCount > 0
                ? `${codebase.releaseCount} release${codebase.releaseCount > 1 ? 's' : ''}`
                : 'No releases'}
            </div>
          )}
        </div>
      </div>

      {/* Edit/delete */}
      {canManage && (
        <div
          className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => onEdit(codebase)}
            className="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
            title="Edit"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(codebase.id)}
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
