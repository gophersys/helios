import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { RefreshCw, Maximize2 } from 'lucide-react';
import { BackButton } from '../../components/ui/back-button';
import { api } from '../../api';
import { useAuth } from '../../auth-provider';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { MetricCard } from '../../components/system/metric-card';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ActionButton } from '../../components/system/action-button';
import { InfoRow } from '../../components/system/info-row';
import { LabelList } from '../../components/system/label-list';
import { ResourceYamlDialog } from '../../components/system/resource-yaml-dialog';
import { DeploymentDetailData } from '../../types/models';

export function DeploymentDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const url = namespace && name ? `/v2/system/deployments/${namespace}/${name}` : null;
  const { data: dep, loading, error, refetch } = useFetchData<DeploymentDetailData>(url);
  const [scaleValue, setScaleValue] = useState<number>(0);
  const [showYaml, setShowYaml] = useState(false);
  const [scaling, setScaling] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const canManage = hasPermission('Concord.Admin.System.Manage');

  // Sync scaleValue when deployment data loads
  if (dep && scaleValue === 0 && dep.replicas.desired !== 0) {
    setScaleValue(dep.replicas.desired);
  }

  const handleScale = async () => {
    if (!namespace || !name) return;
    setScaling(true);
    setMutationError(null);
    try {
      await api(`/v2/system/deployments/${namespace}/${name}/scale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ replicas: scaleValue }),
      });
      await refetch();
    } catch (err: unknown) {
      setMutationError(err instanceof Error ? err.message : 'Failed to scale deployment');
    } finally {
      setScaling(false);
    }
  };

  const handleRestart = async () => {
    if (!namespace || !name) return;
    setRestarting(true);
    setMutationError(null);
    try {
      await api(`/v2/system/deployments/${namespace}/${name}/restart`, { method: 'POST' });
      await refetch();
    } catch (err: unknown) {
      setMutationError(err instanceof Error ? err.message : 'Failed to restart deployment');
    } finally {
      setRestarting(false);
    }
  };

  if (loading) return <LoadingState message="Loading deployment..." />;
  if (!dep) return (
    <div>
      <BackButton label="Back to deployments" onClick={() => navigate('/system/deployments')} />
      <ErrorAlert message={error || 'Deployment not found'} />
    </div>
  );

  return (
    <div>
      <ErrorAlert message={error || mutationError} />

      <BackButton label="Back to deployments" onClick={() => navigate('/system/deployments')} />

      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-text-primary">{dep.name}</h2>
          <StatusIndicator
            status={dep.replicas.available === dep.replicas.desired ? 'Ready' : 'Pending'}
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowYaml(true)}
            className="rounded px-3 py-1.5 text-xs font-medium text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
          >
            YAML
          </button>
          {canManage && (
            <ActionButton
              label={restarting ? 'Restarting...' : 'Restart'}
              icon={RefreshCw}
              variant="warning"
              confirmMessage="Trigger a rolling restart?"
              onConfirm={handleRestart}
              onError={(err) => setMutationError(err.message)}
              disabled={restarting}
            />
          )}
        </div>
      </div>

      <InfoRow items={[
        { label: 'Namespace', value: dep.namespace },
        { label: 'Strategy', value: dep.strategy },
        { label: 'Age', value: dep.age },
      ]} />

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
            aria-label="Replica count"
            className="w-20 rounded border border-border bg-surface-2 px-2 py-1 text-sm text-text-primary"
          />
          <button
            onClick={handleScale}
            disabled={scaling || scaleValue === dep.replicas.desired}
            className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {scaling ? 'Scaling...' : 'Apply'}
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
              <span className="truncate font-mono text-xs text-text-tertiary" title={c.image}>{c.image}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Pods */}
      {dep.pods && dep.pods.length > 0 && (
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-medium text-text-primary">Pods ({dep.pods.length})</h3>
          <div className="overflow-x-auto rounded-lg border border-border">
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
          <div className="overflow-x-auto rounded-lg border border-border">
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
                    <td className="max-w-sm truncate px-3 py-2 text-xs text-text-tertiary" title={c.message}>{c.message}</td>
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
          <LabelList labels={dep.labels} />
        </div>
      )}

      {namespace && name && (
        <ResourceYamlDialog
          kind="deployment"
          namespace={namespace}
          name={name}
          open={showYaml}
          onClose={() => setShowYaml(false)}
        />
      )}
    </div>
  );
}
