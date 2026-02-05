import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Trash2, TerminalSquare } from 'lucide-react';
import { BackButton } from '../../components/ui/back-button';
import { api } from '../../api';
import { useAuth } from '../../auth-provider';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';
import { LogViewer } from '../../components/system/log-viewer';
import { ActionButton } from '../../components/system/action-button';
import { InfoRow } from '../../components/system/info-row';
import { LabelList } from '../../components/system/label-list';
import { CollapsibleSection } from '../../components/system/collapsible-section';
import { ResourceYamlDialog } from '../../components/system/resource-yaml-dialog';
import { Terminal } from '../../components/system/terminal';
import { Select } from '../../components/ui/select';
import { PodDetailData } from '../../types/models';

export function PodDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const url = namespace && name ? `/v2/system/pods/${namespace}/${name}` : null;
  const { data: pod, loading, error, refetch } = useFetchData<PodDetailData>(url);
  const [selectedContainer, setSelectedContainer] = useState('');
  const [showYaml, setShowYaml] = useState(false);
  const [showExec, setShowExec] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const canManage = hasPermission('Concord.Admin.System.Manage');

  // Set initial selected container when pod data loads
  if (pod && pod.containers.length > 0 && !selectedContainer) {
    setSelectedContainer(pod.containers[0].name);
  }

  const handleDelete = async () => {
    if (!namespace || !name) return;
    setDeleting(true);
    try {
      await api(`/v2/system/pods/${namespace}/${name}`, { method: 'DELETE' });
      navigate('/system/pods');
    } catch (err: unknown) {
      // error is handled by ActionButton's onError
      throw err;
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <LoadingState message="Loading pod..." />;
  if (!pod) return (
    <div>
      <BackButton label="Back to pods" onClick={() => navigate('/system/pods')} />
      <ErrorAlert message={error || 'Pod not found'} />
    </div>
  );

  return (
    <div>
      <ErrorAlert message={error || mutationError} />

      <BackButton label="Back to pods" onClick={() => navigate('/system/pods')} />

      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-text-primary">{pod.name}</h2>
          <StatusIndicator status={pod.status} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowYaml(true)}
            className="rounded px-3 py-1.5 text-xs font-medium text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
          >
            YAML
          </button>
          {canManage && pod.status === 'Running' && (
            <button
              onClick={() => setShowExec(!showExec)}
              className="flex items-center gap-1.5 rounded bg-surface-2 px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:bg-surface-3"
            >
              <TerminalSquare size={12} />
              {showExec ? 'Hide Terminal' : 'Exec'}
            </button>
          )}
          {canManage && (
            <ActionButton
              label={deleting ? 'Deleting...' : 'Delete Pod'}
              icon={Trash2}
              variant="danger"
              confirmMessage="Delete this pod? It will be recreated if managed by a controller."
              onConfirm={handleDelete}
              onError={(err) => setMutationError(err.message)}
              disabled={deleting}
            />
          )}
        </div>
      </div>

      <InfoRow items={[
        { label: 'Namespace', value: pod.namespace },
        { label: 'Node', value: pod.nodeName },
        { label: 'IP', value: pod.podIp, mono: true },
        { label: 'SA', value: pod.serviceAccount },
        { label: 'QoS', value: pod.qosClass },
        { label: 'Age', value: pod.age },
      ]} />

      {/* Containers — always visible, compact cards */}
      <div className="mb-4 grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(pod.containers.length, 3)}, 1fr)` }}>
        {pod.containers.map((c) => (
          <div key={c.name} className="rounded-lg border border-border bg-surface-1 p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium text-text-primary">{c.name}</span>
              <StatusIndicator status={c.state === 'running' ? 'Running' : c.state === 'terminated' ? 'Failed' : 'Pending'} />
            </div>
            <div className="truncate font-mono text-2xs text-text-tertiary" title={c.image}>{c.image}</div>
            <div className="mt-1.5 flex gap-4 text-xs text-text-secondary">
              <span>Ready: {c.ready ? 'Yes' : 'No'}</span>
              <span>Restarts: {c.restartCount}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Exec Terminal — shows above everything when active */}
      {showExec && selectedContainer && namespace && pod.name && (
        <div className="mb-4">
          <Terminal
            namespace={namespace}
            pod={pod.name}
            container={selectedContainer}
            onClose={() => setShowExec(false)}
          />
        </div>
      )}

      {/* Logs — collapsible, starts closed */}
      <CollapsibleSection title="Logs">
        <div className="mb-1 flex items-center gap-2">
          {pod.containers.length > 1 && (
            <Select
              compact
              value={selectedContainer}
              onChange={(e) => setSelectedContainer(e.target.value)}
              aria-label="Select container for logs"
            >
              {pod.containers.map((c) => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
            </Select>
          )}
        </div>
        {selectedContainer && namespace && pod.name && (
          <LogViewer namespace={namespace} pod={pod.name} container={selectedContainer} />
        )}
      </CollapsibleSection>

      {/* Conditions */}
      {pod.conditions.length > 0 && (
        <CollapsibleSection title="Conditions" count={pod.conditions.length}>
          <div className="overflow-x-auto rounded-lg border border-border">
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
        </CollapsibleSection>
      )}

      {/* Events */}
      {pod.events.length > 0 && (
        <CollapsibleSection title="Events" count={pod.events.length}>
          <div className="overflow-x-auto rounded-lg border border-border">
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
                {pod.events.map((e) => (
                  <tr key={`${e.type}-${e.reason}-${e.message}-${e.count}`} className="bg-surface-1">
                    <td className="px-3 py-2"><StatusIndicator status={e.type} /></td>
                    <td className="px-3 py-2 text-text-secondary">{e.reason}</td>
                    <td className="max-w-sm truncate px-3 py-2 text-xs text-text-tertiary" title={e.message}>{e.message}</td>
                    <td className="px-3 py-2 text-text-secondary">{e.count}</td>
                    <td className="px-3 py-2"><ResourceAge timestamp={e.lastSeen} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      {/* Labels */}
      {Object.keys(pod.labels).length > 0 && (
        <CollapsibleSection title="Labels" count={Object.keys(pod.labels).length}>
          <LabelList labels={pod.labels} />
        </CollapsibleSection>
      )}

      {namespace && name && (
        <ResourceYamlDialog
          kind="pod"
          namespace={namespace}
          name={name}
          open={showYaml}
          onClose={() => setShowYaml(false)}
        />
      )}
    </div>
  );
}
