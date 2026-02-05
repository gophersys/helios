import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { StatusIndicator } from '../../components/system/status-indicator';
import { ResourceAge } from '../../components/system/resource-age';
import { PodSummary } from '../../types/models';

const POLL_INTERVAL = 5000;

export function PodsList() {
  const navigate = useNavigate();
  const [namespace, setNamespace] = useState('');

  const url = namespace
    ? `/v2/system/pods?namespace=${namespace}&limit=500`
    : '/v2/system/pods?limit=500';
  const { data: pods, loading, error } = useFetchData<PodSummary[]>(url, { pollInterval: POLL_INTERVAL });

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
        <span className={p.restarts > 0 ? 'font-medium text-warning' : 'text-text-secondary'}>
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

  const items = pods ?? [];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {items.length} pod{items.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading pods..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={items}
          keyFn={(p) => `${p.namespace}/${p.name}`}
          onRowClick={(p) => navigate(`/system/pods/${p.namespace}/${p.name}`)}
          emptyMessage="No pods found"
        />
      )}
    </div>
  );
}
