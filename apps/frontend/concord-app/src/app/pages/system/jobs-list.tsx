import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';
import { JobSummary } from '../../types/models';

const POLL_INTERVAL = 5000;

export function JobsList() {
  const navigate = useNavigate();
  const [namespace, setNamespace] = useState('');

  const url = namespace
    ? `/v2/system/jobs?namespace=${namespace}`
    : '/v2/system/jobs';
  const { data: jobs, loading, error } = useFetchData<JobSummary[]>(url, { pollInterval: POLL_INTERVAL });

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

  const items = jobs ?? [];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {items.length} job{items.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading jobs..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={items}
          keyFn={(j) => `${j.namespace}/${j.name}`}
          onRowClick={(j) => navigate(`/system/jobs/${j.namespace}/${j.name}`)}
          emptyMessage="No jobs found"
        />
      )}
    </div>
  );
}
