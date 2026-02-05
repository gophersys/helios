import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { ResourceAge } from '../../components/system/resource-age';
import { ServiceSummary } from '../../types/models';

const POLL_INTERVAL = 15000;

export function ServicesList() {
  const navigate = useNavigate();
  const [namespace, setNamespace] = useState('');

  const url = namespace
    ? `/v2/system/services?namespace=${namespace}`
    : '/v2/system/services';
  const { data: services, loading, error } = useFetchData<ServiceSummary[]>(url, { pollInterval: POLL_INTERVAL });

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

  const items = services ?? [];

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-text-tertiary">
          {items.length} service{items.length !== 1 ? 's' : ''}
        </span>
        <NamespaceSelector value={namespace} onChange={setNamespace} />
      </div>

      {loading ? (
        <LoadingState message="Loading services..." />
      ) : (
        <ResourceTable
          columns={columns}
          data={items}
          keyFn={(s) => `${s.namespace}/${s.name}`}
          onRowClick={(s) => navigate(`/system/services/${s.namespace}/${s.name}`)}
          emptyMessage="No services found"
        />
      )}
    </div>
  );
}
