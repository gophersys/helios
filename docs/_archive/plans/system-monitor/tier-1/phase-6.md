# Phase 6 — Frontend: Nodes List/Detail + Events Feed

## Objective

Build the node list table, the node detail view, and the full events page. This completes Tier 1.

---

## 1. Create `src/app/pages/system/nodes-list.tsx`

Replace the placeholder. Display all nodes in a ResourceTable with click-through to detail.

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';

interface NodeSummary {
  name: string;
  status: string;
  roles: string[];
  internalIp: string;
  kubeletVersion: string;
  capacity: Record<string, string>;
  allocated: { cpuRequests: string; memoryRequests: string; podCount: number };
  createdAt: string;
}

const POLL_INTERVAL = 15000;

export function NodesList() {
  const navigate = useNavigate();
  const [nodes, setNodes] = useState<NodeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNodes = useCallback(async () => {
    try {
      const res = await api<ApiResponse<NodeSummary[]>>('/v2/system/nodes');
      setNodes(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load nodes');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNodes();
    const interval = setInterval(fetchNodes, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchNodes]);

  const columns: Column<NodeSummary>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (n) => <span className="font-medium text-text-primary">{n.name}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (n) => <StatusIndicator status={n.status} />,
    },
    {
      key: 'roles',
      header: 'Roles',
      render: (n) => <span className="text-text-secondary">{n.roles.join(', ')}</span>,
    },
    {
      key: 'ip',
      header: 'Internal IP',
      render: (n) => <span className="font-mono text-xs text-text-secondary">{n.internalIp}</span>,
    },
    {
      key: 'pods',
      header: 'Pods',
      render: (n) => (
        <span className="text-text-secondary">
          {n.allocated.podCount}/{n.capacity.pods || '?'}
        </span>
      ),
    },
    {
      key: 'cpu',
      header: 'CPU Req',
      render: (n) => (
        <span className="text-text-secondary">
          {n.allocated.cpuRequests}/{n.capacity.cpu || '?'}
        </span>
      ),
    },
    {
      key: 'version',
      header: 'Version',
      render: (n) => <span className="text-xs text-text-tertiary">{n.kubeletVersion}</span>,
    },
    {
      key: 'age',
      header: 'Age',
      render: (n) => <ResourceAge timestamp={n.createdAt} />,
    },
  ];

  if (loading) return <LoadingState message="Loading nodes..." />;

  return (
    <div>
      <ErrorAlert message={error} />
      <ResourceTable
        columns={columns}
        data={nodes}
        keyFn={(n) => n.name}
        onRowClick={(n) => navigate(`/system/nodes/${n.name}`)}
        emptyMessage="No nodes found"
      />
    </div>
  );
}
```

---

## 2. Create `src/app/pages/system/node-detail.tsx`

Shows full info for a single node — metric cards for capacity, conditions table, labels, and pod list.

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Cpu, MemoryStick, Box } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { MetricCard } from '../../components/system/metric-card';
import { StatusIndicator } from '../../components/system/status-indicator';

interface NodeDetail {
  name: string;
  status: string;
  roles: string[];
  internalIp: string;
  osImage: string;
  kubeletVersion: string;
  containerRuntime: string;
  architecture: string;
  capacity: Record<string, string>;
  allocatable: Record<string, string>;
  allocated: { cpuRequests: string; memoryRequests: string; podCount: number };
  conditions: { type: string; status: string; reason: string; message: string; lastTransition: string }[];
  labels: Record<string, string>;
  taints: { key: string; value: string; effect: string }[];
  unschedulable: boolean;
  pods: { name: string; namespace: string; status: string; restarts: number }[];
  createdAt: string;
  age: string;
}

export function NodeDetail() {
  const { nodeName } = useParams<{ nodeName: string }>();
  const navigate = useNavigate();
  const [node, setNode] = useState<NodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNode = useCallback(async () => {
    if (!nodeName) return;
    try {
      const res = await api<ApiResponse<NodeDetail>>(`/v2/system/nodes/${nodeName}`);
      setNode(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load node');
    } finally {
      setLoading(false);
    }
  }, [nodeName]);

  useEffect(() => {
    fetchNode();
  }, [fetchNode]);

  if (loading) return <LoadingState message="Loading node..." />;
  if (!node) return <ErrorAlert message={error || 'Node not found'} />;

  return (
    <div>
      <ErrorAlert message={error} />

      {/* Back button + title */}
      <button
        onClick={() => navigate('/system/nodes')}
        className="mb-4 flex items-center gap-1 text-sm text-text-tertiary transition-colors hover:text-text-primary"
      >
        <ArrowLeft size={14} />
        Back to nodes
      </button>

      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-lg font-semibold text-text-primary">{node.name}</h2>
        <StatusIndicator status={node.status} />
        {node.unschedulable && (
          <span className="rounded-full bg-warning-muted px-2 py-0.5 text-xs font-medium text-warning">
            Unschedulable
          </span>
        )}
      </div>

      {/* Info row */}
      <div className="mb-6 flex gap-4 text-xs text-text-tertiary">
        <span>{node.osImage}</span>
        <span className="text-border">|</span>
        <span>{node.containerRuntime}</span>
        <span className="text-border">|</span>
        <span>{node.architecture}</span>
        <span className="text-border">|</span>
        <span>{node.internalIp}</span>
        <span className="text-border">|</span>
        <span>Age: {node.age}</span>
      </div>

      {/* Capacity metric cards */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        <MetricCard
          label="CPU"
          value={node.allocated.cpuRequests}
          icon={Cpu}
          subtitle={`of ${node.allocatable.cpu || node.capacity.cpu || '?'} allocatable`}
        />
        <MetricCard
          label="Memory"
          value={node.allocated.memoryRequests}
          icon={MemoryStick}
          subtitle={`of ${node.allocatable.memory || node.capacity.memory || '?'} allocatable`}
        />
        <MetricCard
          label="Pods"
          value={node.allocated.podCount}
          icon={Box}
          subtitle={`of ${node.allocatable.pods || node.capacity.pods || '?'} allocatable`}
        />
      </div>

      {/* Conditions */}
      <div className="mb-6">
        <h3 className="mb-2 text-sm font-medium text-text-primary">Conditions</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Type</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Status</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Reason</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {node.conditions.map((c) => (
                <tr key={c.type} className="bg-surface-1">
                  <td className="px-3 py-2 font-medium text-text-primary">{c.type}</td>
                  <td className="px-3 py-2">
                    <StatusIndicator status={c.status === 'True' && c.type === 'Ready' ? 'Ready' : c.status === 'False' ? 'Ready' : 'Warning'} />
                  </td>
                  <td className="px-3 py-2 text-text-secondary">{c.reason}</td>
                  <td className="max-w-sm truncate px-3 py-2 text-xs text-text-tertiary">{c.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pods on this node */}
      <div className="mb-6">
        <h3 className="mb-2 text-sm font-medium text-text-primary">
          Pods ({node.pods.length})
        </h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Name</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Namespace</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Status</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Restarts</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {node.pods.map((p) => (
                <tr key={`${p.namespace}/${p.name}`} className="bg-surface-1">
                  <td className="px-3 py-2 font-mono text-xs text-text-primary">{p.name}</td>
                  <td className="px-3 py-2 text-text-secondary">{p.namespace}</td>
                  <td className="px-3 py-2"><StatusIndicator status={p.status} /></td>
                  <td className="px-3 py-2 text-text-secondary">{p.restarts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Labels */}
      {Object.keys(node.labels).length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text-primary">Labels</h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(node.labels).map(([k, v]) => (
              <span
                key={k}
                className="rounded bg-surface-2 px-2 py-0.5 font-mono text-xs text-text-secondary"
              >
                {k}={v}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## 3. Create `src/app/pages/system/events-list.tsx`

Full events page with namespace filter and larger table.

```tsx
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';

interface K8sEvent {
  type: string;
  reason: string;
  message: string;
  object: string;
  namespace: string;
  count: number;
  firstSeen: string | null;
  lastSeen: string | null;
  source: string;
}

const POLL_INTERVAL = 10000;

export function EventsList() {
  const [events, setEvents] = useState<K8sEvent[]>([]);
  const [namespace, setNamespace] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = useCallback(async () => {
    const params = new URLSearchParams({ limit: '200' });
    if (namespace) params.set('namespace', namespace);

    try {
      const res = await api<ApiResponse<K8sEvent[]>>(`/v2/system/events?${params}`);
      setEvents(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load events');
    } finally {
      setLoading(false);
    }
  }, [namespace]);

  useEffect(() => {
    setLoading(true);
    fetchEvents();
    const interval = setInterval(fetchEvents, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchEvents]);

  const columns: Column<K8sEvent>[] = [
    {
      key: 'type',
      header: 'Type',
      render: (e) => <StatusIndicator status={e.type} />,
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (e) => <span className="font-medium text-text-primary">{e.reason}</span>,
    },
    {
      key: 'object',
      header: 'Object',
      render: (e) => <span className="font-mono text-xs text-text-secondary">{e.object}</span>,
    },
    {
      key: 'message',
      header: 'Message',
      render: (e) => (
        <span className="max-w-sm truncate text-xs text-text-tertiary" title={e.message}>
          {e.message}
        </span>
      ),
      className: 'max-w-sm',
    },
    {
      key: 'count',
      header: 'Count',
      render: (e) => <span className="text-text-secondary">{e.count}</span>,
    },
    {
      key: 'age',
      header: 'Last Seen',
      render: (e) => <ResourceAge timestamp={e.lastSeen} />,
    },
  ];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {events.length} event{events.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading events..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={events}
          keyFn={(e, i) => `${e.object}-${e.reason}-${i}`}
          emptyMessage="No events found"
        />
      )}
    </div>
  );
}
```

**Note:** The `keyFn` for events needs an index since events can have duplicate object/reason combos. Update the `ResourceTable` component's `keyFn` type to `(item: T, index: number) => string` and pass `index` in the `.map()` call if needed. Alternatively, use a composite key `${e.object}-${e.reason}-${e.lastSeen}`.

---

## Verification

1. `/system/nodes` — shows all cluster nodes in a table with status, IP, capacity
2. Click a node — navigates to `/system/nodes/<name>` with full detail view
3. Node detail shows metric cards, conditions, pods list, labels
4. `/system/events` — shows events with namespace filter dropdown
5. Namespace selector filters events correctly
6. All pages auto-refresh
7. Light/dark mode works correctly across all pages

---

## Overview Update

Mark all phases complete:

```
- [x] Phase 1 — Backend: permissions, cache, serializers
- [x] Phase 2 — Backend: cluster, node, event services
- [x] Phase 3 — Backend: API routes + router registration
- [x] Phase 4 — Frontend: system page layout, shared components, routing, nav
- [x] Phase 5 — Frontend: cluster overview dashboard
- [x] Phase 6 — Frontend: nodes list/detail + events feed
```

**Tier 1 is complete.** The system page is live with cluster overview, node management, and events monitoring.
