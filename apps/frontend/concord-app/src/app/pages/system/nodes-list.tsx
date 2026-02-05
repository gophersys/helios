import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Server, Cpu, MemoryStick, Box, ChevronRight, Filter } from 'lucide-react';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { StatusIndicator } from '../../components/system/status-indicator';
import { UsageBar } from '../../components/system/usage-bar';
import { ResourceAge } from '../../components/system/resource-age';
import { NodeSummary } from '../../types/models';

import { parseCpuMillis, parseMemoryMi, formatCpu, formatMem } from '../../utils/k8s-resources';

/** Extract meaningful tags from a node's roles + labels. */
function getNodeTags(node: NodeSummary): string[] {
  const tags = new Set<string>();

  // Roles
  for (const role of node.roles) {
    tags.add(role);
  }

  // Status as a tag
  tags.add(node.status);

  // corekinect.com labels — single source of truth for filtering
  const labels = node.labels || {};
  for (const [key, value] of Object.entries(labels)) {
    if (key.startsWith('corekinect.com/') && value) {
      tags.add(value);
    }
  }

  return Array.from(tags);
}

function nodeMatchesFilter(node: NodeSummary, activeFilters: Set<string>): boolean {
  if (activeFilters.size === 0) return true;
  const tags = getNodeTags(node);
  return Array.from(activeFilters).some((f) => tags.includes(f));
}

const POLL_INTERVAL = 15000;

export function NodesList() {
  const navigate = useNavigate();
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());

  const { data: nodes, loading, error } = useFetchData<NodeSummary[]>('/v2/system/nodes', { pollInterval: POLL_INTERVAL });

  const items = nodes ?? [];

  // Collect all available tags across all nodes
  const allTags = useMemo(() => {
    const tagSet = new Set<string>();
    for (const node of items) {
      for (const tag of getNodeTags(node)) {
        tagSet.add(tag);
      }
    }
    return Array.from(tagSet).sort();
  }, [items]);

  const toggleFilter = (tag: string) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  };

  const filteredNodes = useMemo(
    () => items.filter((n) => nodeMatchesFilter(n, activeFilters)),
    [items, activeFilters],
  );

  if (loading) return <LoadingState message="Loading nodes..." />;

  // Aggregate stats (from filtered nodes)
  const readyCount = filteredNodes.filter((n) => n.status === 'Ready').length;
  const totalCpuMillis = filteredNodes.reduce((s, n) => s + parseCpuMillis(n.allocatable?.cpu || n.capacity.cpu || '0'), 0);
  const usedCpuMillis = filteredNodes.reduce((s, n) => s + parseCpuMillis(n.allocated.cpuRequests), 0);
  const totalMemMi = filteredNodes.reduce((s, n) => s + parseMemoryMi(n.allocatable?.memory || n.capacity.memory || '0'), 0);
  const usedMemMi = filteredNodes.reduce((s, n) => s + parseMemoryMi(n.allocated.memoryRequests), 0);
  const totalPodCap = filteredNodes.reduce((s, n) => s + (parseInt(n.allocatable?.pods || n.capacity.pods || '0', 10) || 0), 0);
  const totalPodUsed = filteredNodes.reduce((s, n) => s + n.allocated.podCount, 0);

  return (
    <div>
      <ErrorAlert message={error} />

      {/* Tag filter bar */}
      {allTags.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 text-xs text-text-tertiary">
              <Filter size={12} />
              <span>Filter</span>
            </div>
            {activeFilters.size > 0 && (
              <button
                onClick={() => setActiveFilters(new Set())}
                className="rounded-md px-2 py-1 text-2xs font-medium text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
              >
                Clear all
              </button>
            )}
            <div className="flex flex-wrap gap-1.5">
              {allTags.map((tag) => {
                const isActive = activeFilters.has(tag);
                return (
                  <button
                    key={tag}
                    onClick={() => toggleFilter(tag)}
                    className={[
                      'rounded-full px-2.5 py-1 text-2xs font-medium transition-all',
                      isActive
                        ? 'bg-accent text-white shadow-sm'
                        : 'bg-surface-2 text-text-secondary hover:bg-surface-3 hover:text-text-primary',
                    ].join(' ')}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          </div>
          {activeFilters.size > 0 && (
            <div className="mt-2 text-2xs text-text-tertiary">
              Showing {filteredNodes.length} of {items.length} nodes
            </div>
          )}
        </div>
      )}

      {/* Aggregate summary cards */}
      <div className="mb-6 grid grid-cols-4 gap-3">
        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success-muted">
              <Server size={16} className="text-success" />
            </div>
            <div>
              <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Nodes</div>
              <div className="text-lg font-bold text-text-primary">{readyCount}/{filteredNodes.length}</div>
            </div>
          </div>
          <div className="mt-2 text-2xs text-text-tertiary">
            {readyCount === filteredNodes.length ? (
              <span className="text-success">All nodes ready</span>
            ) : (
              <span className="text-warning">{filteredNodes.length - readyCount} not ready</span>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-info-muted">
              <Cpu size={16} className="text-info" />
            </div>
            <div>
              <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">CPU</div>
            </div>
          </div>
          <UsageBar label="" used={usedCpuMillis} total={totalCpuMillis} formatFn={formatCpu} />
        </div>

        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-muted">
              <MemoryStick size={16} className="text-accent" />
            </div>
            <div>
              <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Memory</div>
            </div>
          </div>
          <UsageBar label="" used={usedMemMi} total={totalMemMi} formatFn={formatMem} />
        </div>

        <div className="rounded-xl border border-border bg-surface-1 p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-warning-muted">
              <Box size={16} className="text-warning" />
            </div>
            <div>
              <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Pods</div>
            </div>
          </div>
          <UsageBar label="" used={totalPodUsed} total={totalPodCap} />
        </div>
      </div>

      {/* Node cards */}
      <div className="space-y-2">
        {filteredNodes.map((node) => {
          const cpuUsed = parseCpuMillis(node.allocated.cpuRequests);
          const cpuTotal = parseCpuMillis(node.allocatable?.cpu || node.capacity.cpu || '0');
          const memUsed = parseMemoryMi(node.allocated.memoryRequests);
          const memTotal = parseMemoryMi(node.allocatable?.memory || node.capacity.memory || '0');
          const podUsed = node.allocated.podCount;
          const podTotal = parseInt(node.allocatable?.pods || node.capacity.pods || '0', 10) || 0;
          const nodeTags = getNodeTags(node);

          return (
            <button
              key={node.name}
              onClick={() => navigate(`/system/nodes/${node.name}`)}
              className="group flex w-full items-start gap-4 rounded-xl border border-border bg-surface-1 p-4 text-left transition-all hover:border-accent/30 hover:shadow-card"
            >
              {/* Status icon */}
              <div
                className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
                  node.status === 'Ready'
                    ? 'bg-success-muted text-success'
                    : 'bg-error-muted text-error'
                }`}
              >
                <Server size={20} />
              </div>

              {/* Info */}
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-sm font-semibold text-text-primary">{node.name}</span>
                  <StatusIndicator status={node.status} />
                  <span className="font-mono text-2xs text-text-tertiary">{node.internalIp}</span>
                  <span className="text-2xs text-text-tertiary">{node.kubeletVersion}</span>
                  <span className="ml-auto text-2xs text-text-tertiary">
                    <ResourceAge timestamp={node.createdAt} />
                  </span>
                  <ChevronRight size={14} className="shrink-0 text-text-tertiary opacity-0 transition-opacity group-hover:opacity-100" />
                </div>

                {/* Tags */}
                <div className="mb-2 flex flex-wrap gap-1">
                  {nodeTags.filter((t) => t !== node.status).map((tag) => (
                    <span
                      key={tag}
                      className={[
                        'rounded-full px-2 py-0.5 text-2xs font-medium',
                        activeFilters.has(tag)
                          ? 'bg-accent-muted text-accent'
                          : 'bg-surface-2 text-text-tertiary',
                      ].join(' ')}
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Usage bars */}
                <div className="grid grid-cols-3 gap-4">
                  <UsageBar label="CPU" used={cpuUsed} total={cpuTotal} formatFn={formatCpu} />
                  <UsageBar label="Memory" used={memUsed} total={memTotal} formatFn={formatMem} />
                  <UsageBar label="Pods" used={podUsed} total={podTotal} />
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {filteredNodes.length === 0 && items.length > 0 && (
        <div className="py-12 text-center text-sm text-text-tertiary">
          No nodes match the selected filters
        </div>
      )}
      {items.length === 0 && (
        <div className="py-12 text-center text-sm text-text-tertiary">No nodes found</div>
      )}
    </div>
  );
}
