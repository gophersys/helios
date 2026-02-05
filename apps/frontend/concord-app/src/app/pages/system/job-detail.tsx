import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
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
import { JobDetailData } from '../../types/models';

export function JobDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const url = namespace && name ? `/v2/system/jobs/${namespace}/${name}` : null;
  const { data: job, loading, error } = useFetchData<JobDetailData>(url);
  const [showYaml, setShowYaml] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const canManage = hasPermission('Concord.Admin.System.Manage');

  const handleDelete = async () => {
    if (!namespace || !name) return;
    setDeleting(true);
    setMutationError(null);
    try {
      await api(`/v2/system/jobs/${namespace}/${name}`, { method: 'DELETE' });
      navigate('/system/jobs');
    } catch (err: unknown) {
      throw err;
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <LoadingState message="Loading job..." />;
  if (!job) return (
    <div>
      <BackButton label="Back to jobs" onClick={() => navigate('/system/jobs')} />
      <ErrorAlert message={error || 'Job not found'} />
    </div>
  );

  return (
    <div>
      <ErrorAlert message={error || mutationError} />

      <BackButton label="Back to jobs" onClick={() => navigate('/system/jobs')} />

      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-text-primary">{job.name}</h2>
          <StatusIndicator status={job.status === 'Complete' ? 'Succeeded' : job.status} />
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
              label={deleting ? 'Deleting...' : 'Delete Job'}
              icon={Trash2}
              variant="danger"
              confirmMessage="Delete this job and its pods?"
              onConfirm={handleDelete}
              onError={(err) => setMutationError(err.message)}
              disabled={deleting}
            />
          )}
        </div>
      </div>

      <InfoRow items={[
        { label: 'Namespace', value: job.namespace },
        { label: 'Duration', value: job.duration || '-' },
        { label: 'Backoff Limit', value: String(job.backoffLimit) },
        { label: 'Age', value: job.age },
      ]} />

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
          <div className="overflow-x-auto rounded-lg border border-border">
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
          <LabelList labels={job.labels} />
        </div>
      )}

      {namespace && name && (
        <ResourceYamlDialog
          kind="job"
          namespace={namespace}
          name={name}
          open={showYaml}
          onClose={() => setShowYaml(false)}
        />
      )}
    </div>
  );
}
