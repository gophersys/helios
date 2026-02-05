import { useParams, useNavigate } from 'react-router-dom';
import { Cpu, MemoryStick, Box, Server, Tag, Shield } from 'lucide-react';
import { BackButton } from '../../components/ui/back-button';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { StatusIndicator } from '../../components/system/status-indicator';
import { UsageBar } from '../../components/system/usage-bar';
import { ProgressRing } from '../../components/system/progress-ring';
import { LabelList } from '../../components/system/label-list';

interface NodeDetailData {
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
  annotations: Record<string, string>;
  taints: { key: string; value: string; effect: string }[];
  unschedulable: boolean;
  pods: { name: string; namespace: string; status: string; restarts: number }[];
  createdAt: string;
  age: string;
}

import { parseCpuMillis, parseMemoryMi, formatCpu, formatMem } from '../../utils/k8s-resources';

export function NodeDetail() {
  const { nodeName } = useParams<{ nodeName: string }>();
  const navigate = useNavigate();
  const url = nodeName ? `/v2/system/nodes/${nodeName}` : null;
  const { data: node, loading, error } = useFetchData<NodeDetailData>(url);

  if (loading) return <LoadingState message="Loading node..." />;
  if (!node) return (
    <div>
      <BackButton label="Back to nodes" onClick={() => navigate('/system/nodes')} />
      <ErrorAlert message={error || 'Node not found'} />
    </div>
  );

  const cpuUsed = parseCpuMillis(node.allocated.cpuRequests);
  const cpuTotal = parseCpuMillis(node.allocatable.cpu || node.capacity.cpu || '0');
  const memUsed = parseMemoryMi(node.allocated.memoryRequests);
  const memTotal = parseMemoryMi(node.allocatable.memory || node.capacity.memory || '0');
  const podUsed = node.allocated.podCount;
  const podTotal = parseInt(node.allocatable.pods || node.capacity.pods || '0', 10) || 0;

  return (
    <div>
      <ErrorAlert message={error} />

      <BackButton label="Back to nodes" onClick={() => navigate('/system/nodes')} />

      {/* Header card */}
      <div className="mb-6 rounded-xl border border-border bg-surface-1 p-5">
        <div className="flex items-start gap-4">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${
              node.status === 'Ready'
                ? 'bg-success-muted text-success'
                : 'bg-error-muted text-error'
            }`}
          >
            <Server size={24} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-text-primary">{node.name}</h2>
              <StatusIndicator status={node.status} />
              {node.unschedulable && (
                <span className="rounded-full bg-warning-muted px-2 py-0.5 text-xs font-medium text-warning">
                  Unschedulable
                </span>
              )}
            </div>
            <div className="mt-2 flex gap-1.5">
              {node.roles.map((role) => (
                <span key={role} className="rounded bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
                  {role}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Info grid — clean key/value pairs */}
        <div className="mt-4 grid grid-cols-3 gap-x-6 gap-y-2 border-t border-border pt-4">
          <div>
            <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Internal IP</div>
            <div className="mt-0.5 font-mono text-sm text-text-primary">{node.internalIp}</div>
          </div>
          <div>
            <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">OS Image</div>
            <div className="mt-0.5 text-sm text-text-primary">{node.osImage}</div>
          </div>
          <div>
            <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Architecture</div>
            <div className="mt-0.5 text-sm text-text-primary">{node.architecture}</div>
          </div>
          <div>
            <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Container Runtime</div>
            <div className="mt-0.5 text-sm text-text-primary">{node.containerRuntime}</div>
          </div>
          <div>
            <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Kubelet Version</div>
            <div className="mt-0.5 text-sm text-text-primary">{node.kubeletVersion}</div>
          </div>
          <div>
            <div className="text-2xs font-medium uppercase tracking-wide text-text-tertiary">Age</div>
            <div className="mt-0.5 text-sm text-text-primary">{node.age}</div>
          </div>
        </div>
      </div>

      {/* Resource usage — ring shows %, bar shows actual values */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-surface-1 p-5">
          <div className="flex w-full items-center gap-2">
            <Cpu size={14} className="text-info" />
            <span className="text-xs font-medium text-text-primary">CPU Requests</span>
          </div>
          <ProgressRing value={cpuUsed} max={cpuTotal} size={100} strokeWidth={8} />
          <div className="w-full">
            <UsageBar label="" used={cpuUsed} total={cpuTotal} formatFn={formatCpu} />
          </div>
        </div>

        <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-surface-1 p-5">
          <div className="flex w-full items-center gap-2">
            <MemoryStick size={14} className="text-accent" />
            <span className="text-xs font-medium text-text-primary">Memory Requests</span>
          </div>
          <ProgressRing value={memUsed} max={memTotal} size={100} strokeWidth={8} />
          <div className="w-full">
            <UsageBar label="" used={memUsed} total={memTotal} formatFn={formatMem} />
          </div>
        </div>

        <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-surface-1 p-5">
          <div className="flex w-full items-center gap-2">
            <Box size={14} className="text-warning" />
            <span className="text-xs font-medium text-text-primary">Pods</span>
          </div>
          <ProgressRing
            value={podUsed}
            max={podTotal}
            size={100}
            strokeWidth={8}
            centerText={`${podUsed}/${podTotal}`}
          />
          <div className="w-full">
            <UsageBar label="" used={podUsed} total={podTotal} />
          </div>
        </div>
      </div>

      {/* Conditions */}
      <div className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <Shield size={14} className="text-text-tertiary" />
          <h3 className="text-sm font-medium text-text-primary">Conditions</h3>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {node.conditions.map((c) => {
            const isHealthy =
              (c.type === 'Ready' && c.status === 'True') ||
              (c.type !== 'Ready' && c.status === 'False');
            return (
              <div
                key={c.type}
                className={`rounded-lg border p-3 ${
                  isHealthy
                    ? 'border-success/20 bg-success-muted'
                    : 'border-warning/20 bg-warning-muted'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-text-primary">{c.type}</span>
                  <StatusIndicator status={isHealthy ? 'Ready' : 'Warning'} />
                </div>
                {c.reason && (
                  <div className="mt-1 text-2xs text-text-secondary">{c.reason}</div>
                )}
                {c.message && (
                  <div className="mt-0.5 truncate text-2xs text-text-tertiary" title={c.message}>
                    {c.message}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Pods on this node */}
      <div className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <Box size={14} className="text-text-tertiary" />
          <h3 className="text-sm font-medium text-text-primary">Pods ({node.pods.length})</h3>
        </div>
        {node.pods.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface-1 py-6 text-center text-sm text-text-tertiary">
            No pods running on this node
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
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
                  <tr
                    key={`${p.namespace}/${p.name}`}
                    className="cursor-pointer bg-surface-1 transition-colors hover:bg-surface-2"
                    onClick={() => navigate(`/system/pods/${p.namespace}/${p.name}`)}
                  >
                    <td className="px-3 py-2 font-mono text-xs text-text-primary">{p.name}</td>
                    <td className="px-3 py-2 text-text-secondary">{p.namespace}</td>
                    <td className="px-3 py-2"><StatusIndicator status={p.status} /></td>
                    <td className="px-3 py-2">
                      <span className={p.restarts > 0 ? 'font-medium text-warning' : 'text-text-secondary'}>
                        {p.restarts}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Labels + Taints */}
      <div className="grid grid-cols-2 gap-4">
        {Object.keys(node.labels).length > 0 && (
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Tag size={14} className="text-text-tertiary" />
              <h3 className="text-sm font-medium text-text-primary">Labels ({Object.keys(node.labels).length})</h3>
            </div>
            <div className="max-h-48 overflow-y-auto rounded-lg border border-border bg-surface-1 p-3">
              <LabelList labels={node.labels} />
            </div>
          </div>
        )}

        {node.taints.length > 0 && (
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Shield size={14} className="text-text-tertiary" />
              <h3 className="text-sm font-medium text-text-primary">Taints ({node.taints.length})</h3>
            </div>
            <div className="rounded-lg border border-border bg-surface-1 p-3">
              <div className="space-y-1.5">
                {node.taints.map((t) => (
                  <div key={`${t.key}-${t.effect}`} className="flex items-center gap-2">
                    <span className="rounded bg-warning-muted px-1.5 py-0.5 text-2xs font-medium text-warning">
                      {t.effect}
                    </span>
                    <span className="font-mono text-2xs text-text-secondary">
                      {t.key}{t.value ? `=${t.value}` : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
