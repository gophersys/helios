# Phase 5 — Frontend: Pod List/Detail + Log Viewer + Tab Expansion

## Objective

Expand the system page sub-navigation to include all Tier 2 resource tabs. Build the pod list, pod detail, and the log viewer component.

---

## 0. Install dependencies

```bash
yarn add socket.io-client
```

This is required for the log viewer's SocketIO connection.

---

## 1. Modify `src/app/pages/system/system-page.tsx`

Add new tabs and route imports. Update the `tabs` array:

```tsx
import { Activity, HardDrive, Bell, Box, Layers, Globe, Briefcase, FileText } from 'lucide-react';

const tabs = [
  { to: '/system', label: 'Overview', icon: Activity, end: true },
  { to: '/system/nodes', label: 'Nodes', icon: HardDrive },
  { to: '/system/pods', label: 'Pods', icon: Box },
  { to: '/system/deployments', label: 'Deployments', icon: Layers },
  { to: '/system/services', label: 'Services', icon: Globe },
  { to: '/system/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/system/config', label: 'Config', icon: FileText },
  { to: '/system/events', label: 'Events', icon: Bell },
];
```

Also make the tab bar horizontally scrollable for smaller screens by adding `overflow-x-auto` to the wrapper:

```tsx
<div className="mb-6 flex gap-1 overflow-x-auto rounded-lg bg-surface-2 p-0.5">
```

---

## 2. Modify `src/app/app.tsx`

Add imports for new pages and routes.

**Imports** (add with existing system imports):

```tsx
import { PodsList } from './pages/system/pods-list';
import { PodDetail } from './pages/system/pod-detail';
import { DeploymentsList } from './pages/system/deployments-list';
import { DeploymentDetail } from './pages/system/deployment-detail';
import { ServicesList } from './pages/system/services-list';
import { ServiceDetail } from './pages/system/service-detail';
import { JobsList } from './pages/system/jobs-list';
import { JobDetail } from './pages/system/job-detail';
import { ConfigList } from './pages/system/config-list';
```

**Routes** (add inside the `<Route path="system">` block, after existing child routes):

```tsx
<Route path="pods" element={<PodsList />} />
<Route path="pods/:namespace/:name" element={<PodDetail />} />
<Route path="deployments" element={<DeploymentsList />} />
<Route path="deployments/:namespace/:name" element={<DeploymentDetail />} />
<Route path="services" element={<ServicesList />} />
<Route path="services/:namespace/:name" element={<ServiceDetail />} />
<Route path="jobs" element={<JobsList />} />
<Route path="jobs/:namespace/:name" element={<JobDetail />} />
<Route path="config" element={<ConfigList />} />
```

---

## 3. Create `src/app/components/system/log-viewer.tsx`

Terminal-style log display component with SocketIO streaming.

```tsx
import { useEffect, useRef, useState } from 'react';
import { io, type Socket } from 'socket.io-client';
import { Play, Square, Trash2, ArrowDown } from 'lucide-react';

interface LogViewerProps {
  namespace: string;
  pod: string;
  container: string;
}

export function LogViewer({ namespace, pod, container }: LogViewerProps) {
  const [lines, setLines] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (socketRef.current) {
        socketRef.current.emit('unsubscribe_logs', { namespace, pod, container });
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, [namespace, pod, container]);

  useEffect(() => {
    if (autoScrollRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines]);

  const startStream = () => {
    setError(null);
    setLines([]);

    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:9001';
    const socket = io(`${apiBase}/system`, {
      transports: ['websocket'],
      auth: {
        token: localStorage.getItem('token') || '',
      },
    });

    socket.on('connect', () => {
      socket.emit('subscribe_logs', {
        namespace,
        pod,
        container,
        tailLines: 200,
      });
      setStreaming(true);
    });

    socket.on('log_line', (data: { line: string }) => {
      setLines((prev) => {
        const next = [...prev, data.line];
        // Cap at 5000 lines to prevent memory issues
        return next.length > 5000 ? next.slice(-5000) : next;
      });
    });

    socket.on('log_error', (data: { message: string }) => {
      setError(data.message);
      setStreaming(false);
    });

    socket.on('disconnect', () => {
      setStreaming(false);
    });

    socketRef.current = socket;
  };

  const stopStream = () => {
    if (socketRef.current) {
      socketRef.current.emit('unsubscribe_logs', { namespace, pod, container });
      socketRef.current.disconnect();
      socketRef.current = null;
    }
    setStreaming(false);
  };

  const clearLogs = () => {
    setLines([]);
  };

  const scrollToBottom = () => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  };

  const handleScroll = () => {
    if (containerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
      autoScrollRef.current = scrollHeight - scrollTop - clientHeight < 50;
    }
  };

  return (
    <div className="flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 rounded-t-lg border border-b-0 border-border bg-surface-2 px-3 py-2">
        {!streaming ? (
          <button
            onClick={startStream}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-success transition-colors hover:bg-surface-1"
          >
            <Play size={12} />
            Stream
          </button>
        ) : (
          <button
            onClick={stopStream}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-error transition-colors hover:bg-surface-1"
          >
            <Square size={12} />
            Stop
          </button>
        )}
        <button
          onClick={clearLogs}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-tertiary transition-colors hover:bg-surface-1 hover:text-text-primary"
        >
          <Trash2 size={12} />
          Clear
        </button>
        <button
          onClick={scrollToBottom}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-tertiary transition-colors hover:bg-surface-1 hover:text-text-primary"
        >
          <ArrowDown size={12} />
          Bottom
        </button>
        <span className="ml-auto text-2xs text-text-tertiary">
          {lines.length} lines
        </span>
      </div>

      {/* Log output */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-96 overflow-auto rounded-b-lg border border-border bg-[#1a1a2e] p-3 font-mono text-xs leading-5 text-green-400 dark:bg-[#0d0d1a]"
      >
        {error && (
          <div className="mb-2 text-error">{error}</div>
        )}
        {lines.length === 0 && !streaming && !error && (
          <div className="text-text-tertiary">Click "Stream" to start viewing logs</div>
        )}
        {lines.map((line, i) => (
          <div key={i} className="whitespace-pre-wrap break-all hover:bg-white/5">
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 4. Create `src/app/components/system/action-button.tsx`

Button with confirmation dialog for mutating actions.

```tsx
import { useState } from 'react';
import { type LucideIcon } from 'lucide-react';

interface ActionButtonProps {
  label: string;
  icon: LucideIcon;
  variant: 'danger' | 'warning' | 'primary';
  confirmMessage: string;
  onConfirm: () => Promise<void>;
  disabled?: boolean;
}

const variantStyles = {
  danger: 'bg-error text-white hover:bg-error/90',
  warning: 'bg-warning text-white hover:bg-warning/90',
  primary: 'bg-accent text-white hover:bg-accent/90',
};

export function ActionButton({
  label,
  icon: Icon,
  variant,
  confirmMessage,
  onConfirm,
  disabled = false,
}: ActionButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleClick = () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setLoading(true);
    onConfirm()
      .then(() => setConfirming(false))
      .catch(() => setConfirming(false))
      .finally(() => setLoading(false));
  };

  const handleCancel = () => {
    setConfirming(false);
  };

  if (confirming) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-secondary">{confirmMessage}</span>
        <button
          onClick={handleClick}
          disabled={loading}
          className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${variantStyles[variant]} ${
            loading ? 'opacity-50' : ''
          }`}
        >
          {loading ? 'Working...' : 'Confirm'}
        </button>
        <button
          onClick={handleCancel}
          disabled={loading}
          className="rounded px-3 py-1.5 text-xs font-medium text-text-tertiary transition-colors hover:text-text-primary"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled}
      className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
        variantStyles[variant]
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <Icon size={12} />
      {label}
    </button>
  );
}
```

---

## 5. Create `src/app/pages/system/pods-list.tsx`

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';

interface PodSummary {
  name: string;
  namespace: string;
  status: string;
  ready: string;
  restarts: number;
  nodeName: string;
  createdAt: string;
}

const POLL_INTERVAL = 10000;

export function PodsList() {
  const navigate = useNavigate();
  const [pods, setPods] = useState<PodSummary[]>([]);
  const [namespace, setNamespace] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPods = useCallback(async () => {
    const params = new URLSearchParams();
    if (namespace) params.set('namespace', namespace);

    try {
      const res = await api<ApiResponse<PodSummary[]>>(`/v2/system/pods?${params}`);
      setPods(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load pods');
    } finally {
      setLoading(false);
    }
  }, [namespace]);

  useEffect(() => {
    setLoading(true);
    fetchPods();
    const interval = setInterval(fetchPods, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchPods]);

  const columns: Column<PodSummary>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (p) => <span className="font-medium text-text-primary">{p.name}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      render: (p) => <span className="text-text-secondary">{p.namespace}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (p) => <StatusIndicator status={p.status} />,
    },
    {
      key: 'ready',
      header: 'Ready',
      render: (p) => <span className="text-text-secondary">{p.ready}</span>,
    },
    {
      key: 'restarts',
      header: 'Restarts',
      render: (p) => (
        <span className={p.restarts > 5 ? 'text-warning' : 'text-text-secondary'}>
          {p.restarts}
        </span>
      ),
    },
    {
      key: 'node',
      header: 'Node',
      render: (p) => <span className="text-xs text-text-tertiary">{p.nodeName}</span>,
    },
    {
      key: 'age',
      header: 'Age',
      render: (p) => <ResourceAge timestamp={p.createdAt} />,
    },
  ];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {pods.length} pod{pods.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading pods..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={pods}
          keyFn={(p) => `${p.namespace}/${p.name}`}
          onRowClick={(p) => navigate(`/system/pods/${p.namespace}/${p.name}`)}
          emptyMessage="No pods found"
        />
      )}
    </div>
  );
}
```

---

## 6. Create `src/app/pages/system/pod-detail.tsx`

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Trash2 } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { useAuth } from '../../auth-provider';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';
import { LogViewer } from '../../components/system/log-viewer';
import { ActionButton } from '../../components/system/action-button';

interface PodDetailData {
  name: string;
  namespace: string;
  status: string;
  ready: string;
  restarts: number;
  nodeName: string;
  podIp: string;
  serviceAccount: string;
  qosClass: string;
  containers: {
    name: string;
    image: string;
    ready: boolean;
    restartCount: number;
    state: string;
  }[];
  conditions: {
    type: string;
    status: string;
    reason: string;
    message: string;
    lastTransition: string;
  }[];
  volumes: { name: string; type: string }[];
  events: {
    type: string;
    reason: string;
    message: string;
    lastSeen: string | null;
    count: number;
  }[];
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export function PodDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [pod, setPod] = useState<PodDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedContainer, setSelectedContainer] = useState('');

  const canManage = hasPermission('Concord.Admin.System.Manage');

  const fetchPod = useCallback(async () => {
    if (!namespace || !name) return;
    try {
      const res = await api<ApiResponse<PodDetailData>>(`/v2/system/pods/${namespace}/${name}`);
      setPod(res.data);
      if (res.data.containers.length > 0 && !selectedContainer) {
        setSelectedContainer(res.data.containers[0].name);
      }
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load pod');
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => {
    fetchPod();
  }, [fetchPod]);

  const handleDelete = async () => {
    if (!namespace || !name) return;
    await api(`/v2/system/pods/${namespace}/${name}`, { method: 'DELETE' });
    navigate('/system/pods');
  };

  if (loading) return <LoadingState message="Loading pod..." />;
  if (!pod) return <ErrorAlert message={error || 'Pod not found'} />;

  return (
    <div>
      <ErrorAlert message={error} />

      <button
        onClick={() => navigate('/system/pods')}
        className="mb-4 flex items-center gap-1 text-sm text-text-tertiary transition-colors hover:text-text-primary"
      >
        <ArrowLeft size={14} />
        Back to pods
      </button>

      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-text-primary">{pod.name}</h2>
          <StatusIndicator status={pod.status} />
        </div>
        {canManage && (
          <ActionButton
            label="Delete Pod"
            icon={Trash2}
            variant="danger"
            confirmMessage="Delete this pod? It will be recreated if managed by a controller."
            onConfirm={handleDelete}
          />
        )}
      </div>

      {/* Info row */}
      <div className="mb-6 flex flex-wrap gap-4 text-xs text-text-tertiary">
        <span>Namespace: <span className="text-text-secondary">{pod.namespace}</span></span>
        <span className="text-border">|</span>
        <span>Node: <span className="text-text-secondary">{pod.nodeName}</span></span>
        <span className="text-border">|</span>
        <span>IP: <span className="font-mono text-text-secondary">{pod.podIp}</span></span>
        <span className="text-border">|</span>
        <span>SA: <span className="text-text-secondary">{pod.serviceAccount}</span></span>
        <span className="text-border">|</span>
        <span>QoS: <span className="text-text-secondary">{pod.qosClass}</span></span>
        <span className="text-border">|</span>
        <span>Age: <span className="text-text-secondary">{pod.age}</span></span>
      </div>

      {/* Containers */}
      <div className="mb-6">
        <h3 className="mb-2 text-sm font-medium text-text-primary">Containers</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Name</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Image</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">State</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Ready</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Restarts</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {pod.containers.map((c) => (
                <tr key={c.name} className="bg-surface-1">
                  <td className="px-3 py-2 font-medium text-text-primary">{c.name}</td>
                  <td className="px-3 py-2 font-mono text-xs text-text-secondary">{c.image}</td>
                  <td className="px-3 py-2"><StatusIndicator status={c.state === 'running' ? 'Running' : c.state === 'terminated' ? 'Failed' : 'Pending'} /></td>
                  <td className="px-3 py-2 text-text-secondary">{c.ready ? 'Yes' : 'No'}</td>
                  <td className="px-3 py-2 text-text-secondary">{c.restartCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Log Viewer */}
      <div className="mb-6">
        <div className="mb-2 flex items-center gap-3">
          <h3 className="text-sm font-medium text-text-primary">Logs</h3>
          {pod.containers.length > 1 && (
            <select
              value={selectedContainer}
              onChange={(e) => setSelectedContainer(e.target.value)}
              className="rounded-md border border-border bg-surface-1 px-2 py-1 text-xs text-text-primary"
            >
              {pod.containers.map((c) => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
            </select>
          )}
        </div>
        {selectedContainer && namespace && pod.name && (
          <LogViewer namespace={namespace} pod={pod.name} container={selectedContainer} />
        )}
      </div>

      {/* Conditions */}
      {pod.conditions.length > 0 && (
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-medium text-text-primary">Conditions</h3>
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Type</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Status</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Reason</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Age</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {pod.conditions.map((c) => (
                  <tr key={c.type} className="bg-surface-1">
                    <td className="px-3 py-2 font-medium text-text-primary">{c.type}</td>
                    <td className="px-3 py-2"><StatusIndicator status={c.status === 'True' ? 'Ready' : 'Pending'} /></td>
                    <td className="px-3 py-2 text-text-secondary">{c.reason}</td>
                    <td className="px-3 py-2"><ResourceAge timestamp={c.lastTransition} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Events */}
      {pod.events.length > 0 && (
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-medium text-text-primary">Events</h3>
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Type</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Reason</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Message</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Count</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Age</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {pod.events.map((e, idx) => (
                  <tr key={`${e.reason}-${idx}`} className="bg-surface-1">
                    <td className="px-3 py-2"><StatusIndicator status={e.type} /></td>
                    <td className="px-3 py-2 text-text-secondary">{e.reason}</td>
                    <td className="max-w-sm truncate px-3 py-2 text-xs text-text-tertiary">{e.message}</td>
                    <td className="px-3 py-2 text-text-secondary">{e.count}</td>
                    <td className="px-3 py-2"><ResourceAge timestamp={e.lastSeen} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Labels */}
      {Object.keys(pod.labels).length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text-primary">Labels</h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(pod.labels).map(([k, v]) => (
              <span key={k} className="rounded bg-surface-2 px-2 py-0.5 font-mono text-xs text-text-secondary">
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

## Verification

1. Frontend compiles without errors
2. Tab bar shows all 8 tabs: Overview, Nodes, Pods, Deployments, Services, Jobs, Config, Events
3. `/system/pods` — shows pod table with namespace filter
4. Click a pod — navigates to `/system/pods/<ns>/<name>`
5. Pod detail shows containers, log viewer, conditions, events, labels
6. Log viewer connects via SocketIO and streams logs
7. Delete button appears only for users with `System.Manage`
8. Tab bar scrolls on smaller screens

---

## Overview Update

```
- [x] Phase 5 — Frontend: pod list/detail + log viewer + system page tab expansion
```
