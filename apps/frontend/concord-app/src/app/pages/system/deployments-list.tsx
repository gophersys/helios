import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { ResourceAge } from '../../components/system/resource-age';
import { DeploymentSummary } from '../../types/models';

const POLL_INTERVAL = 5000;

export function DeploymentsList() {
  const navigate = useNavigate();
  const [namespace, setNamespace] = useState('');

  const url = namespace
    ? `/v2/system/deployments?namespace=${namespace}`
    : '/v2/system/deployments';
  const { data: deployments, loading, error } = useFetchData<DeploymentSummary[]>(url, { pollInterval: POLL_INTERVAL });

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

  const items = deployments ?? [];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {items.length} deployment{items.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading deployments..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={items}
          keyFn={(d) => `${d.namespace}/${d.name}`}
          onRowClick={(d) => navigate(`/system/deployments/${d.namespace}/${d.name}`)}
          emptyMessage="No deployments found"
        />
      )}
    </div>
  );
}
