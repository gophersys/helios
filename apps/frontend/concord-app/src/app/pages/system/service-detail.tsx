import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BackButton } from '../../components/ui/back-button';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { InfoRow } from '../../components/system/info-row';
import { LabelList } from '../../components/system/label-list';
import { ResourceYamlDialog } from '../../components/system/resource-yaml-dialog';
import { ServiceDetailData } from '../../types/models';

export function ServiceDetail() {
  const { namespace, name } = useParams<{ namespace: string; name: string }>();
  const navigate = useNavigate();
  const url = namespace && name ? `/v2/system/services/${namespace}/${name}` : null;
  const { data: svc, loading, error } = useFetchData<ServiceDetailData>(url);
  const [showYaml, setShowYaml] = useState(false);

  if (loading) return <LoadingState message="Loading service..." />;
  if (!svc) return (
    <div>
      <BackButton label="Back to services" onClick={() => navigate('/system/services')} />
      <ErrorAlert message={error || 'Service not found'} />
    </div>
  );

  const infoItems = [
    { label: 'Namespace', value: svc.namespace },
    { label: 'Type', value: svc.type },
    { label: 'Cluster IP', value: svc.clusterIp, mono: true },
    ...(svc.loadBalancerIp ? [{ label: 'LB IP', value: svc.loadBalancerIp, mono: true }] : []),
    { label: 'Age', value: svc.age },
  ];

  return (
    <div>
      <ErrorAlert message={error} />

      <BackButton label="Back to services" onClick={() => navigate('/system/services')} />

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-bold text-text-primary">{svc.name}</h2>
        <button
          onClick={() => setShowYaml(true)}
          className="rounded px-3 py-1.5 text-xs font-medium text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
        >
          YAML
        </button>
      </div>

      <InfoRow items={infoItems} />

      {/* Ports */}
      <div className="mb-6">
        <h3 className="mb-2 text-sm font-medium text-text-primary">Ports</h3>
        <div className="overflow-x-auto rounded-lg border border-border">
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
              {svc.ports.map((p) => (
                <tr key={`${p.port}-${p.protocol}`} className="bg-surface-1">
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
            {svc.endpoints.map((ep) => (
              <div key={`${ep.addresses.join(',')}-${ep.ports.map((p) => `${p.port}/${p.protocol}`).join(',')}`} className="rounded-lg border border-border bg-surface-1 p-3">
                <div className="text-xs text-text-tertiary">
                  Addresses: <span className="break-all font-mono text-text-secondary">{ep.addresses.join(', ')}</span>
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
          <LabelList labels={svc.selector} />
        </div>
      )}

      {namespace && name && (
        <ResourceYamlDialog
          kind="service"
          namespace={namespace}
          name={name}
          open={showYaml}
          onClose={() => setShowYaml(false)}
        />
      )}
    </div>
  );
}
