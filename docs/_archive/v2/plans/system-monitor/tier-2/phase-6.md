# Phase 6 — Frontend: Deployments, Services, Jobs, Config Pages

## Objective

Build the remaining Tier 2 frontend pages: deployments (with scale/restart), services, jobs, and config (configmaps + secrets). This completes Tier 2.

---

## 1. Create `src/app/pages/system/deployments-list.tsx`

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

interface DeploymentSummary {
  name: string;
  namespace: string;
  replicas: { desired: number; ready: number; available: number; updated: number };
  strategy: string;
  containers: { name: string; image: string }[];
  createdAt: string;
}

const POLL_INTERVAL = 10000;

export function DeploymentsList() {
  const navigate = useNavigate();
  const [deployments, setDeployments] = useState<DeploymentSummary[]>([]);
  const [namespace, setNamespace] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDeployments = useCallback(async () => {
    const params = new URLSearchParams();
    if (namespace) params.set('namespace', namespace);

    try {
      const res = await api<ApiResponse<DeploymentSummary[]>>(`/v2/system/deployments?${params}`);
      setDeployments(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load deployments');
    } finally {
      setLoading(false);
    }
  }, [namespace]);

  useEffect(() => {
    setLoading(true);
    fetchDeployments();
    const interval = setInterval(fetchDeployments, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchDeployments]);

  const columns: Column<DeploymentSummary>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (d) => <span className="font-medium text-text-primary">{d.name}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      render: (d) => <span className="text-text-secondary">{d.namespace}</span>,
    },
    {
      key: 'replicas',
      header: 'Ready',
      render: (d) => {
        const allReady = d.replicas.ready === d.replicas.desired && d.replicas.desired > 0;
        return (
          <span className={allReady ? 'text-success' : 'text-warning'}>
            {d.replicas.ready}/{d.replicas.desired}
          </span>
        );
      },
    },
    {
      key: 'strategy',
      header: 'Strategy',
      render: (d) => <span className="text-xs text-text-tertiary">{d.strategy}</span>,
    },
    {
      key: 'image',
      header: 'Image',
      render: (d) => (
        <span className="font-mono text-xs text-text-secondary">
          {d.containers[0]?.image || '-'}
        </span>
      ),
    },
    {
      key: 'age',
      header: 'Age',
      render: (d) => <ResourceAge timestamp={d.createdAt} />,
    },
  ];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {deployments.length} deployment{deployments.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading deployments..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={deployments}
          keyFn={(d) => `${d.namespace}/${d.name}`}
          onRowClick={(d) => navigate(`/system/deployments/${d.namespace}/${d.name}`)}
          emptyMessage="No deployments found"
        />
      )}
    </div>
  );
}
```

---

## 2. Create `src/app/pages/system/deployment-detail.tsx`

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Maximize2 } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { useAuth } from '../../auth-provider';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { MetricCard } from '../../components/system/metric-card';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ActionButton } from '../../components/system/action-button';

interface DeploymentDetailData {
  name: string;
  namespace: string;
  replicas: { desired: number; ready: number; available: number; updated: number };
  strategy: string;
  containers: { name: string; image: string }[];
  conditions: { type: string; status: string; reason: string; message: string; lastTransition: string }[];
  selector: Record<string, string>;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  pods: { name: string; status: string; ready: boolean; restarts: number; nodeName: string }[];
  createdAt: string;
  age: string;
}

export function DeploymentDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [dep, setDep] = useState<DeploymentDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scaleValue, setScaleValue] = useState<number>(0);

  const canManage = hasPermission('Concord.Admin.System.Manage');

  const fetchDeployment = useCallback(async () => {
    if (!namespace || !name) return;
    try {
      const res = await api<ApiResponse<DeploymentDetailData>>(`/v2/system/deployments/${namespace}/${name}`);
      setDep(res.data);
      setScaleValue(res.data.replicas.desired);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load deployment');
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => {
    fetchDeployment();
  }, [fetchDeployment]);

  const handleScale = async () => {
    if (!namespace || !name) return;
    await api(`/v2/system/deployments/${namespace}/${name}/scale`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ replicas: scaleValue }),
    });
    fetchDeployment();
  };

  const handleRestart = async () => {
    if (!namespace || !name) return;
    await api(`/v2/system/deployments/${namespace}/${name}/restart`, { method: 'POST' });
    fetchDeployment();
  };

  if (loading) return <LoadingState message="Loading deployment..." />;
  if (!dep) return <ErrorAlert message={error || 'Deployment not found'} />;

  return (
    <div>
      <ErrorAlert message={error} />

      <button
        onClick={() => navigate('/system/deployments')}
        className="mb-4 flex items-center gap-1 text-sm text-text-tertiary transition-colors hover:text-text-primary"
      >
        <ArrowLeft size={14} />
        Back to deployments
      </button>

      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-text-primary">{dep.name}</h2>
          <StatusIndicator
            status={dep.replicas.available === dep.replicas.desired ? 'Ready' : 'Pending'}
          />
        </div>
        {canManage && (
          <div className="flex items-center gap-2">
            <ActionButton
              label="Restart"
              icon={RefreshCw}
              variant="warning"
              confirmMessage="Trigger a rolling restart?"
              onConfirm={handleRestart}
            />
          </div>
        )}
      </div>

      {/* Info row */}
      <div className="mb-6 flex gap-4 text-xs text-text-tertiary">
        <span>Namespace: <span className="text-text-secondary">{dep.namespace}</span></span>
        <span className="text-border">|</span>
        <span>Strategy: <span className="text-text-secondary">{dep.strategy}</span></span>
        <span className="text-border">|</span>
        <span>Age: <span className="text-text-secondary">{dep.age}</span></span>
      </div>

      {/* Replica metric cards */}
      <div className="mb-6 grid grid-cols-4 gap-3">
        <MetricCard label="Desired" value={dep.replicas.desired} status="neutral" />
        <MetricCard label="Ready" value={dep.replicas.ready} status={dep.replicas.ready === dep.replicas.desired ? 'success' : 'warning'} />
        <MetricCard label="Available" value={dep.replicas.available} status="neutral" />
        <MetricCard label="Updated" value={dep.replicas.updated} status="neutral" />
      </div>

      {/* Scale control */}
      {canManage && (
        <div className="mb-6 flex items-center gap-3 rounded-lg border border-border bg-surface-1 p-4">
          <Maximize2 size={14} className="text-text-tertiary" />
          <span className="text-sm text-text-secondary">Scale replicas:</span>
          <input
            type="number"
            min={0}
            max={100}
            value={scaleValue}
            onChange={(e) => setScaleValue(parseInt(e.target.value) || 0)}
            className="w-20 rounded border border-border bg-surface-2 px-2 py-1 text-sm text-text-primary"
          />
          <button
            onClick={handleScale}
            disabled={scaleValue === dep.replicas.desired}
            className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Apply
          </button>
        </div>
      )}

      {/* Containers */}
      <div className="mb-6">
        <h3 className="mb-2 text-sm font-medium text-text-primary">Container Images</h3>
        <div className="flex flex-col gap-1">
          {dep.containers.map((c) => (
            <div key={c.name} className="flex gap-2 text-sm">
              <span className="text-text-secondary">{c.name}:</span>
              <span className="font-mono text-xs text-text-tertiary">{c.image}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Pods */}
      {dep.pods && dep.pods.length > 0 && (
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-medium text-text-primary">Pods ({dep.pods.length})</h3>
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Name</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Status</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Ready</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Restarts</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Node</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {dep.pods.map((p) => (
                  <tr
                    key={p.name}
                    className="cursor-pointer bg-surface-1 transition-colors hover:bg-surface-2"
                    onClick={() => navigate(`/system/pods/${dep.namespace}/${p.name}`)}
                  >
                    <td className="px-3 py-2 font-mono text-xs text-text-primary">{p.name}</td>
                    <td className="px-3 py-2"><StatusIndicator status={p.status} /></td>
                    <td className="px-3 py-2 text-text-secondary">{p.ready ? 'Yes' : 'No'}</td>
                    <td className="px-3 py-2 text-text-secondary">{p.restarts}</td>
                    <td className="px-3 py-2 text-xs text-text-tertiary">{p.nodeName}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Conditions */}
      {dep.conditions.length > 0 && (
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
                {dep.conditions.map((c) => (
                  <tr key={c.type} className="bg-surface-1">
                    <td className="px-3 py-2 font-medium text-text-primary">{c.type}</td>
                    <td className="px-3 py-2"><StatusIndicator status={c.status === 'True' ? 'Ready' : 'Pending'} /></td>
                    <td className="px-3 py-2 text-text-secondary">{c.reason}</td>
                    <td className="max-w-sm truncate px-3 py-2 text-xs text-text-tertiary">{c.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Labels */}
      {Object.keys(dep.labels).length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text-primary">Labels</h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(dep.labels).map(([k, v]) => (
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

## 3. Create `src/app/pages/system/services-list.tsx`

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { ResourceAge } from '../../components/system/resource-age';

interface ServiceSummary {
  name: string;
  namespace: string;
  type: string;
  clusterIp: string;
  ports: { name: string; port: number; targetPort: string; protocol: string }[];
  createdAt: string;
}

const POLL_INTERVAL = 15000;

export function ServicesList() {
  const navigate = useNavigate();
  const [services, setServices] = useState<ServiceSummary[]>([]);
  const [namespace, setNamespace] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchServices = useCallback(async () => {
    const params = new URLSearchParams();
    if (namespace) params.set('namespace', namespace);

    try {
      const res = await api<ApiResponse<ServiceSummary[]>>(`/v2/system/services?${params}`);
      setServices(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load services');
    } finally {
      setLoading(false);
    }
  }, [namespace]);

  useEffect(() => {
    setLoading(true);
    fetchServices();
    const interval = setInterval(fetchServices, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchServices]);

  const columns: Column<ServiceSummary>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (s) => <span className="font-medium text-text-primary">{s.name}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      render: (s) => <span className="text-text-secondary">{s.namespace}</span>,
    },
    {
      key: 'type',
      header: 'Type',
      render: (s) => <span className="text-text-secondary">{s.type}</span>,
    },
    {
      key: 'clusterIp',
      header: 'Cluster IP',
      render: (s) => <span className="font-mono text-xs text-text-secondary">{s.clusterIp}</span>,
    },
    {
      key: 'ports',
      header: 'Ports',
      render: (s) => (
        <span className="font-mono text-xs text-text-secondary">
          {s.ports.map((p) => `${p.port}/${p.protocol}`).join(', ')}
        </span>
      ),
    },
    {
      key: 'age',
      header: 'Age',
      render: (s) => <ResourceAge timestamp={s.createdAt} />,
    },
  ];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {services.length} service{services.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading services..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={services}
          keyFn={(s) => `${s.namespace}/${s.name}`}
          onRowClick={(s) => navigate(`/system/services/${s.namespace}/${s.name}`)}
          emptyMessage="No services found"
        />
      )}
    </div>
  );
}
```

---

## 4. Create `src/app/pages/system/service-detail.tsx`

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';

interface ServiceDetailData {
  name: string;
  namespace: string;
  type: string;
  clusterIp: string;
  externalIps: string[];
  loadBalancerIp: string | null;
  ports: { name: string; port: number; targetPort: string; protocol: string; nodePort: number | null }[];
  selector: Record<string, string>;
  endpoints: { addresses: string[]; ports: { port: number; protocol: string }[] }[];
  createdAt: string;
  age: string;
}

export function ServiceDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const [svc, setSvc] = useState<ServiceDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchService = useCallback(async () => {
    if (!namespace || !name) return;
    try {
      const res = await api<ApiResponse<ServiceDetailData>>(`/v2/system/services/${namespace}/${name}`);
      setSvc(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load service');
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => {
    fetchService();
  }, [fetchService]);

  if (loading) return <LoadingState message="Loading service..." />;
  if (!svc) return <ErrorAlert message={error || 'Service not found'} />;

  return (
    <div>
      <ErrorAlert message={error} />

      <button
        onClick={() => navigate('/system/services')}
        className="mb-4 flex items-center gap-1 text-sm text-text-tertiary transition-colors hover:text-text-primary"
      >
        <ArrowLeft size={14} />
        Back to services
      </button>

      <div className="mb-4">
        <h2 className="text-lg font-semibold text-text-primary">{svc.name}</h2>
      </div>

      <div className="mb-6 flex gap-4 text-xs text-text-tertiary">
        <span>Namespace: <span className="text-text-secondary">{svc.namespace}</span></span>
        <span className="text-border">|</span>
        <span>Type: <span className="text-text-secondary">{svc.type}</span></span>
        <span className="text-border">|</span>
        <span>Cluster IP: <span className="font-mono text-text-secondary">{svc.clusterIp}</span></span>
        {svc.loadBalancerIp && (
          <>
            <span className="text-border">|</span>
            <span>LB IP: <span className="font-mono text-text-secondary">{svc.loadBalancerIp}</span></span>
          </>
        )}
        <span className="text-border">|</span>
        <span>Age: <span className="text-text-secondary">{svc.age}</span></span>
      </div>

      {/* Ports */}
      <div className="mb-6">
        <h3 className="mb-2 text-sm font-medium text-text-primary">Ports</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Name</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Port</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Target Port</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Protocol</th>
                <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Node Port</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {svc.ports.map((p, idx) => (
                <tr key={idx} className="bg-surface-1">
                  <td className="px-3 py-2 text-text-primary">{p.name || '-'}</td>
                  <td className="px-3 py-2 font-mono text-text-secondary">{p.port}</td>
                  <td className="px-3 py-2 font-mono text-text-secondary">{p.targetPort}</td>
                  <td className="px-3 py-2 text-text-secondary">{p.protocol}</td>
                  <td className="px-3 py-2 font-mono text-text-secondary">{p.nodePort || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Endpoints */}
      <div className="mb-6">
        <h3 className="mb-2 text-sm font-medium text-text-primary">Endpoints</h3>
        {svc.endpoints.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface-1 p-4 text-center text-sm text-text-tertiary">
            No endpoints
          </div>
        ) : (
          <div className="space-y-2">
            {svc.endpoints.map((ep, idx) => (
              <div key={idx} className="rounded-lg border border-border bg-surface-1 p-3">
                <div className="text-xs text-text-tertiary">
                  Addresses: <span className="font-mono text-text-secondary">{ep.addresses.join(', ')}</span>
                </div>
                <div className="text-xs text-text-tertiary">
                  Ports: <span className="font-mono text-text-secondary">{ep.ports.map((p) => `${p.port}/${p.protocol}`).join(', ')}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Selector */}
      {Object.keys(svc.selector).length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text-primary">Selector</h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(svc.selector).map(([k, v]) => (
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

## 5. Create `src/app/pages/system/jobs-list.tsx`

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

interface JobSummary {
  name: string;
  namespace: string;
  completions: string;
  status: string;
  active: number;
  succeeded: number;
  failed: number;
  duration: string;
  createdAt: string;
}

const POLL_INTERVAL = 10000;

export function JobsList() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [namespace, setNamespace] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    const params = new URLSearchParams();
    if (namespace) params.set('namespace', namespace);

    try {
      const res = await api<ApiResponse<JobSummary[]>>(`/v2/system/jobs?${params}`);
      setJobs(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs');
    } finally {
      setLoading(false);
    }
  }, [namespace]);

  useEffect(() => {
    setLoading(true);
    fetchJobs();
    const interval = setInterval(fetchJobs, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const columns: Column<JobSummary>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (j) => <span className="font-medium text-text-primary">{j.name}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      render: (j) => <span className="text-text-secondary">{j.namespace}</span>,
    },
    {
      key: 'completions',
      header: 'Completions',
      render: (j) => <span className="text-text-secondary">{j.completions}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (j) => <StatusIndicator status={j.status === 'Complete' ? 'Succeeded' : j.status} />,
    },
    {
      key: 'duration',
      header: 'Duration',
      render: (j) => <span className="text-xs text-text-tertiary">{j.duration || '-'}</span>,
    },
    {
      key: 'age',
      header: 'Age',
      render: (j) => <ResourceAge timestamp={j.createdAt} />,
    },
  ];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {jobs.length} job{jobs.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading jobs..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={jobs}
          keyFn={(j) => `${j.namespace}/${j.name}`}
          onRowClick={(j) => navigate(`/system/jobs/${j.namespace}/${j.name}`)}
          emptyMessage="No jobs found"
        />
      )}
    </div>
  );
}
```

---

## 6. Create `src/app/pages/system/job-detail.tsx`

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Trash2 } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { useAuth } from '../../auth-provider';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { MetricCard } from '../../components/system/metric-card';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ActionButton } from '../../components/system/action-button';

interface JobDetailData {
  name: string;
  namespace: string;
  completions: string;
  parallelism: number;
  active: number;
  succeeded: number;
  failed: number;
  status: string;
  duration: string;
  backoffLimit: number;
  conditions: { type: string; status: string; reason: string; message: string }[];
  pods: { name: string; status: string; restarts: number }[];
  labels: Record<string, string>;
  createdAt: string;
  age: string;
}

export function JobDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [job, setJob] = useState<JobDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canManage = hasPermission('Concord.Admin.System.Manage');

  const fetchJob = useCallback(async () => {
    if (!namespace || !name) return;
    try {
      const res = await api<ApiResponse<JobDetailData>>(`/v2/system/jobs/${namespace}/${name}`);
      setJob(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load job');
    } finally {
      setLoading(false);
    }
  }, [namespace, name]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  const handleDelete = async () => {
    if (!namespace || !name) return;
    await api(`/v2/system/jobs/${namespace}/${name}`, { method: 'DELETE' });
    navigate('/system/jobs');
  };

  if (loading) return <LoadingState message="Loading job..." />;
  if (!job) return <ErrorAlert message={error || 'Job not found'} />;

  return (
    <div>
      <ErrorAlert message={error} />

      <button
        onClick={() => navigate('/system/jobs')}
        className="mb-4 flex items-center gap-1 text-sm text-text-tertiary transition-colors hover:text-text-primary"
      >
        <ArrowLeft size={14} />
        Back to jobs
      </button>

      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-text-primary">{job.name}</h2>
          <StatusIndicator status={job.status === 'Complete' ? 'Succeeded' : job.status} />
        </div>
        {canManage && (
          <ActionButton
            label="Delete Job"
            icon={Trash2}
            variant="danger"
            confirmMessage="Delete this job and its pods?"
            onConfirm={handleDelete}
          />
        )}
      </div>

      <div className="mb-6 flex gap-4 text-xs text-text-tertiary">
        <span>Namespace: <span className="text-text-secondary">{job.namespace}</span></span>
        <span className="text-border">|</span>
        <span>Duration: <span className="text-text-secondary">{job.duration || '-'}</span></span>
        <span className="text-border">|</span>
        <span>Backoff Limit: <span className="text-text-secondary">{job.backoffLimit}</span></span>
        <span className="text-border">|</span>
        <span>Age: <span className="text-text-secondary">{job.age}</span></span>
      </div>

      <div className="mb-6 grid grid-cols-4 gap-3">
        <MetricCard label="Active" value={job.active} status={job.active > 0 ? 'info' : 'neutral'} />
        <MetricCard label="Succeeded" value={job.succeeded} status="success" />
        <MetricCard label="Failed" value={job.failed} status={job.failed > 0 ? 'error' : 'neutral'} />
        <MetricCard label="Parallelism" value={job.parallelism} status="neutral" />
      </div>

      {/* Pods */}
      {job.pods.length > 0 && (
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-medium text-text-primary">Pods ({job.pods.length})</h3>
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Name</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Status</th>
                  <th className="px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary">Restarts</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {job.pods.map((p) => (
                  <tr
                    key={p.name}
                    className="cursor-pointer bg-surface-1 transition-colors hover:bg-surface-2"
                    onClick={() => navigate(`/system/pods/${job.namespace}/${p.name}`)}
                  >
                    <td className="px-3 py-2 font-mono text-xs text-text-primary">{p.name}</td>
                    <td className="px-3 py-2"><StatusIndicator status={p.status} /></td>
                    <td className="px-3 py-2 text-text-secondary">{p.restarts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Labels */}
      {Object.keys(job.labels).length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text-primary">Labels</h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(job.labels).map(([k, v]) => (
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

## 7. Create `src/app/pages/system/config-list.tsx`

Tabbed view for ConfigMaps and Secrets.

```tsx
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { ResourceAge } from '../../components/system/resource-age';

interface ConfigMapSummary {
  name: string;
  namespace: string;
  dataKeys: string[];
  dataCount: number;
  createdAt: string;
}

interface SecretSummary {
  name: string;
  namespace: string;
  type: string;
  dataKeys: string[];
  dataCount: number;
  createdAt: string;
}

type Tab = 'configmaps' | 'secrets';

const POLL_INTERVAL = 15000;

export function ConfigList() {
  const [tab, setTab] = useState<Tab>('configmaps');
  const [configmaps, setConfigmaps] = useState<ConfigMapSummary[]>([]);
  const [secrets, setSecrets] = useState<SecretSummary[]>([]);
  const [namespace, setNamespace] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    const params = new URLSearchParams();
    if (namespace) params.set('namespace', namespace);

    try {
      if (tab === 'configmaps') {
        const res = await api<ApiResponse<ConfigMapSummary[]>>(`/v2/system/configmaps?${params}`);
        setConfigmaps(res.data);
      } else {
        const res = await api<ApiResponse<SecretSummary[]>>(`/v2/system/secrets?${params}`);
        setSecrets(res.data);
      }
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to load ${tab}`);
    } finally {
      setLoading(false);
    }
  }, [tab, namespace]);

  useEffect(() => {
    setLoading(true);
    fetchData();
    const interval = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  const cmColumns: Column<ConfigMapSummary>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (cm) => <span className="font-medium text-text-primary">{cm.name}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      render: (cm) => <span className="text-text-secondary">{cm.namespace}</span>,
    },
    {
      key: 'keys',
      header: 'Keys',
      render: (cm) => (
        <span className="text-xs text-text-tertiary" title={cm.dataKeys.join(', ')}>
          {cm.dataCount} key{cm.dataCount !== 1 ? 's' : ''}
        </span>
      ),
    },
    {
      key: 'age',
      header: 'Age',
      render: (cm) => <ResourceAge timestamp={cm.createdAt} />,
    },
  ];

  const secretColumns: Column<SecretSummary>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (s) => <span className="font-medium text-text-primary">{s.name}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      render: (s) => <span className="text-text-secondary">{s.namespace}</span>,
    },
    {
      key: 'type',
      header: 'Type',
      render: (s) => <span className="text-xs text-text-tertiary">{s.type}</span>,
    },
    {
      key: 'keys',
      header: 'Keys',
      render: (s) => (
        <span className="text-xs text-text-tertiary" title={s.dataKeys.join(', ')}>
          {s.dataCount} key{s.dataCount !== 1 ? 's' : ''}
        </span>
      ),
    },
    {
      key: 'age',
      header: 'Age',
      render: (s) => <ResourceAge timestamp={s.createdAt} />,
    },
  ];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <div className="flex gap-1 rounded-md bg-surface-2 p-0.5">
          <button
            onClick={() => setTab('configmaps')}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-all ${
              tab === 'configmaps'
                ? 'bg-surface-1 text-text-primary shadow-sm'
                : 'text-text-tertiary hover:text-text-secondary'
            }`}
          >
            ConfigMaps
          </button>
          <button
            onClick={() => setTab('secrets')}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-all ${
              tab === 'secrets'
                ? 'bg-surface-1 text-text-primary shadow-sm'
                : 'text-text-tertiary hover:text-text-secondary'
            }`}
          >
            Secrets
          </button>
        </div>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message={`Loading ${tab}...`} />
      ) : tab === 'configmaps' ? (
        <ResourceTable
          columns={cmColumns}
          data={configmaps}
          keyFn={(cm) => `${cm.namespace}/${cm.name}`}
          emptyMessage="No configmaps found"
        />
      ) : (
        <ResourceTable
          columns={secretColumns}
          data={secrets}
          keyFn={(s) => `${s.namespace}/${s.name}`}
          emptyMessage="No secrets found"
        />
      )}
    </div>
  );
}
```

---

## Verification

1. Frontend compiles without errors
2. `/system/deployments` — shows deployment table, click navigates to detail
3. Deployment detail shows replica metrics, scale input, restart button (System.Manage only)
4. Scale and restart actions work correctly
5. `/system/services` — shows service table, click navigates to detail with ports and endpoints
6. `/system/jobs` — shows job table, click navigates to detail with pod list and delete button
7. `/system/config` — shows configmap/secret toggle, tables for each type
8. All pages have namespace filter and auto-refresh

---

## Overview Update

Mark all phases complete:

```
- [x] Phase 1 — Backend: serializers for pods, deployments, services, jobs, configmaps, secrets
- [x] Phase 2 — Backend: service modules for all resource types
- [x] Phase 3 — Backend: REST API routes + mutating actions
- [x] Phase 4 — Backend: pod log streaming via SocketIO
- [x] Phase 5 — Frontend: pod list/detail + log viewer + system page tab expansion
- [x] Phase 6 — Frontend: deployments, services, jobs, config pages
```

**Tier 2 is complete.** The system monitor now has a full resource browser with pod logs, deployment scale/restart, and config viewing.
