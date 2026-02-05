import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  ChevronDown,
  ChevronRight,
  Search,
  ChevronLeft,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { useAuth } from '../../auth-provider';
import { api } from '../../api';
import { ApiResponse } from '../../types';
import { formatTimeAgo, formatDateTime } from '../../utils/formatting';
import { EmptyState } from '../../components/ui/empty-state';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { PageHeader } from '../../components/ui/page-header';
import { Select } from '../../components/ui/select';
import { AuditEntry, Pagination } from '../../types/models';

const ENTITY_TYPES = [
  'User',
  'PermissionSet',
  'ApiKey',
  'MTIB',
  'InventoryComponent',
  'ComponentRevision',
  'InventoryAssembly',
  'AssemblyRevision',
  'Codebase',
  'Release',
  'Artifact',
];

function getVerbPastTense(verb: string): string {
  const map: Record<string, string> = {
    create: 'created',
    update: 'updated',
    delete: 'deleted',
    deactivate: 'deactivated',
    register: 'registered',
    unregister: 'unregistered',
    upload: 'uploaded',
  };
  return map[verb] || verb;
}

function formatAction(action: string): { verb: string; entity: string } {
  const parts = action.split('.');
  if (parts.length >= 2) {
    const verb = parts[parts.length - 1];
    const entity = parts.slice(0, -1).join(' ');
    return { verb: getVerbPastTense(verb), entity };
  }
  return { verb: action, entity: '' };
}

function DetailValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-text-tertiary">null</span>;
  }
  if (typeof value === 'boolean') {
    return (
      <span className={value ? 'text-success' : 'text-error'}>
        {String(value)}
      </span>
    );
  }
  if (typeof value === 'object') {
    return (
      <pre className="mt-1 max-h-40 overflow-auto rounded bg-surface-0 p-2 text-2xs text-text-secondary">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <span className="text-text-primary">{String(value)}</span>;
}

export function HistoryPage() {
  const { hasPermission } = useAuth();

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [pagination, setPagination] = useState<Pagination>({
    page: 1,
    limit: 50,
    total: 0,
    pages: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters
  const [entityType, setEntityType] = useState('');
  const [actionSearch, setActionSearch] = useState('');
  const [page, setPage] = useState(1);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '50');
      if (entityType) params.set('entityType', entityType);
      if (actionSearch) params.set('action', actionSearch);

      const res = await api<
        ApiResponse<{ entries: AuditEntry[]; pagination: Pagination }>
      >('/v2/admin/history?' + params.toString());

      setEntries(res.data.entries);
      setPagination(res.data.pagination);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  }, [page, entityType, actionSearch]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [entityType, actionSearch]);

  if (!hasPermission('Concord.Admin.History.View')) {
    return <Navigate to="/" replace />;
  }

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="History"
          description="Audit log of actions across the system (last 30 days)."
        />
      </div>

      <ErrorAlert message={error} />

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
          />
          <input
            type="text"
            value={actionSearch}
            onChange={(e) => setActionSearch(e.target.value)}
            placeholder="Search actions..."
            className="rounded-lg border border-border bg-surface-0 py-2 pl-8 pr-3 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </div>
        <Select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="w-auto"
        >
          <option value="">All entity types</option>
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
        <span className="ml-auto text-2xs text-text-tertiary">
          {pagination.total} entries
        </span>
      </div>

      {/* Table */}
      {loading ? (
        <LoadingState message="Loading history..." />
      ) : entries.length === 0 ? (
        <EmptyState message="No audit entries found." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-1">
                <th className="w-8 px-3 py-3" />
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Action
                </th>
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Entity
                </th>
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  User
                </th>
                <th className="px-4 py-3 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  When
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const isExpanded = expandedId === entry.id;
                const { verb, entity } = formatAction(entry.action);
                const hasDetails =
                  entry.details &&
                  Object.keys(entry.details).length > 0;

                return (
                  <tr
                    key={entry.id}
                    className="group border-b border-border-subtle last:border-0"
                  >
                    <td colSpan={5} className="p-0">
                      <div>
                        <button
                          onClick={() => hasDetails && toggleExpand(entry.id)}
                          className={[
                            'flex w-full items-center text-left transition-colors',
                            hasDetails
                              ? 'cursor-pointer hover:bg-surface-1'
                              : 'cursor-default',
                          ].join(' ')}
                        >
                          <div className="w-8 shrink-0 px-3 py-3">
                            {hasDetails &&
                              (isExpanded ? (
                                <ChevronDown
                                  size={14}
                                  className="text-text-tertiary"
                                />
                              ) : (
                                <ChevronRight
                                  size={14}
                                  className="text-text-tertiary"
                                />
                              ))}
                          </div>
                          <div className="flex-1 px-4 py-3">
                            <span className="font-medium text-text-primary">
                              {verb}
                            </span>
                            {entity && (
                              <span className="ml-1 text-text-secondary">
                                {entity}
                              </span>
                            )}
                          </div>
                          <div className="shrink-0 px-4 py-3">
                            <span className="inline-flex items-center rounded-full bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">
                              {entry.entityType}
                            </span>
                            {entry.entityId && (
                              <span className="ml-2 font-mono text-2xs text-text-tertiary">
                                {entry.entityId.length > 12
                                  ? entry.entityId.slice(0, 12) + '...'
                                  : entry.entityId}
                              </span>
                            )}
                          </div>
                          <div className="shrink-0 px-4 py-3">
                            {entry.user ? (
                              <span className="text-text-secondary">
                                {entry.user.name}
                              </span>
                            ) : (
                              <span className="text-text-tertiary">
                                System
                              </span>
                            )}
                          </div>
                          <div className="shrink-0 px-4 py-3 text-right">
                            <span
                              className="text-text-tertiary"
                              title={formatDateTime(entry.createdAt)}
                            >
                              {formatTimeAgo(entry.createdAt)}
                            </span>
                          </div>
                        </button>

                        {/* Expanded details */}
                        {isExpanded && hasDetails && (
                          <div className="border-t border-border-subtle bg-surface-1 px-12 py-4">
                            <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                              {Object.entries(entry.details!).map(
                                ([key, value]) => (
                                  <div key={key}>
                                    <div className="text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                                      {key}
                                    </div>
                                    <div className="mt-0.5 text-sm">
                                      <DetailValue value={value} />
                                    </div>
                                  </div>
                                )
                              )}
                            </div>
                            <div className="mt-3 flex items-center gap-4 text-2xs text-text-tertiary">
                              <span>{formatDateTime(entry.createdAt)}</span>
                              {entry.ipAddress && (
                                <span>IP: {entry.ipAddress}</span>
                              )}
                              <span className="font-mono">
                                {entry.id}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {pagination.pages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <span className="text-2xs text-text-tertiary">
            Page {pagination.page} of {pagination.pages}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(1)}
              disabled={page <= 1}
              aria-label="First page"
              className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              <ChevronsLeft size={14} />
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              aria-label="Previous page"
              className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(pagination.pages, p + 1))}
              disabled={page >= pagination.pages}
              aria-label="Next page"
              className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              <ChevronRight size={14} />
            </button>
            <button
              onClick={() => setPage(pagination.pages)}
              disabled={page >= pagination.pages}
              aria-label="Last page"
              className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
            >
              <ChevronsRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
