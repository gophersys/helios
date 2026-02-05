import { useState } from 'react';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { ResourceAge } from '../../components/system/resource-age';
import { ConfigMapSummary, SecretSummary } from '../../types/models';

type Tab = 'configmaps' | 'secrets';

const POLL_INTERVAL = 15000;

export function ConfigList() {
  const [tab, setTab] = useState<Tab>('configmaps');
  const [namespace, setNamespace] = useState('');

  const cmUrl = namespace
    ? `/v2/system/configmaps?namespace=${namespace}`
    : '/v2/system/configmaps';
  const secretUrl = namespace
    ? `/v2/system/secrets?namespace=${namespace}`
    : '/v2/system/secrets';

  const { data: configmaps, loading: cmLoading, error: cmError } = useFetchData<ConfigMapSummary[]>(
    cmUrl,
    { pollInterval: POLL_INTERVAL, enabled: tab === 'configmaps' }
  );
  const { data: secrets, loading: secretLoading, error: secretError } = useFetchData<SecretSummary[]>(
    secretUrl,
    { pollInterval: POLL_INTERVAL, enabled: tab === 'secrets' }
  );

  const loading = tab === 'configmaps' ? cmLoading : secretLoading;
  const error = tab === 'configmaps' ? cmError : secretError;

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
          data={configmaps ?? []}
          keyFn={(cm) => `${cm.namespace}/${cm.name}`}
          emptyMessage="No configmaps found"
        />
      ) : (
        <ResourceTable
          columns={secretColumns}
          data={secrets ?? []}
          keyFn={(s) => `${s.namespace}/${s.name}`}
          emptyMessage="No secrets found"
        />
      )}
    </div>
  );
}
