import { useState } from 'react';
import { useFetchData } from '../../hooks/use-fetch-data';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { ResourceAge } from '../../components/system/resource-age';
import { Role, RoleBinding, ServiceAccount } from '../../types/models';

type RbacTab = 'roles' | 'clusterroles' | 'bindings' | 'clusterrolebindings' | 'serviceaccounts';

type RbacData = Role | RoleBinding | ServiceAccount;

const TABS: { key: RbacTab; label: string; namespaced: boolean }[] = [
  { key: 'roles', label: 'Roles', namespaced: true },
  { key: 'clusterroles', label: 'ClusterRoles', namespaced: false },
  { key: 'bindings', label: 'RoleBindings', namespaced: true },
  { key: 'clusterrolebindings', label: 'ClusterRoleBindings', namespaced: false },
  { key: 'serviceaccounts', label: 'ServiceAccounts', namespaced: true },
];

const API_PATHS: Record<RbacTab, string> = {
  roles: '/v2/system/rbac/roles',
  clusterroles: '/v2/system/rbac/clusterroles',
  bindings: '/v2/system/rbac/bindings',
  clusterrolebindings: '/v2/system/rbac/clusterrolebindings',
  serviceaccounts: '/v2/system/rbac/serviceaccounts',
};

function isRole(item: RbacData): item is Role {
  return 'rules' in item;
}

function isRoleBinding(item: RbacData): item is RoleBinding {
  return 'roleRef' in item;
}

function isServiceAccount(item: RbacData): item is ServiceAccount {
  return 'secrets' in item;
}

export function RbacPage() {
  const [tab, setTab] = useState<RbacTab>('roles');
  const [namespace, setNamespace] = useState('');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  const isNamespaced = TABS.find((t) => t.key === tab)!.namespaced;

  const url = (() => {
    const params = new URLSearchParams();
    if (namespace && isNamespaced) {
      params.set('namespace', namespace);
    }
    const qs = params.toString();
    return qs ? `${API_PATHS[tab]}?${qs}` : API_PATHS[tab];
  })();

  const { data, loading, error } = useFetchData<RbacData[]>(url);

  const items = data ?? [];

  const roleColumns: Column<Role>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (r) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setExpandedRule(expandedRule === r.name ? null : r.name);
          }}
          className="font-medium text-accent hover:underline"
        >
          {r.name}
        </button>
      ),
    },
    ...(tab === 'roles'
      ? [
          {
            key: 'namespace' as const,
            header: 'Namespace',
            render: (r: Role) => <span className="text-text-secondary">{r.namespace}</span>,
          },
        ]
      : []),
    {
      key: 'rules',
      header: 'Rules',
      render: (r) => (
        <span className="text-text-secondary">
          {r.rules.length} rule{r.rules.length !== 1 ? 's' : ''}
        </span>
      ),
    },
    {
      key: 'age',
      header: 'Age',
      render: (r) => <ResourceAge timestamp={r.createdAt} />,
    },
  ];

  const bindingColumns: Column<RoleBinding>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (b) => <span className="font-medium text-text-primary">{b.name}</span>,
    },
    ...(tab === 'bindings'
      ? [
          {
            key: 'namespace' as const,
            header: 'Namespace',
            render: (b: RoleBinding) => <span className="text-text-secondary">{b.namespace}</span>,
          },
        ]
      : []),
    {
      key: 'roleRef',
      header: 'Role',
      render: (b) => (
        <span className="text-text-secondary">
          <span className="text-2xs text-text-tertiary">{b.roleRef.kind}/</span>
          {b.roleRef.name}
        </span>
      ),
    },
    {
      key: 'subjects',
      header: 'Subjects',
      render: (b) => (
        <div className="flex flex-wrap gap-1">
          {b.subjects.map((s, i) => (
            <span key={`${s.kind}-${s.name}-${s.namespace}-${i}`} className="rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
              {s.kind}/{s.name}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: 'age',
      header: 'Age',
      render: (b) => <ResourceAge timestamp={b.createdAt} />,
    },
  ];

  const saColumns: Column<ServiceAccount>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (sa) => <span className="font-medium text-text-primary">{sa.name}</span>,
    },
    {
      key: 'namespace',
      header: 'Namespace',
      render: (sa) => <span className="text-text-secondary">{sa.namespace}</span>,
    },
    {
      key: 'secrets',
      header: 'Secrets',
      render: (sa) => <span className="text-text-secondary">{sa.secrets.length}</span>,
    },
    {
      key: 'age',
      header: 'Age',
      render: (sa) => <ResourceAge timestamp={sa.createdAt} />,
    },
  ];

  const renderExpandedRules = (role: Role) => (
    <div className="mt-2 rounded border border-border bg-surface-2 p-3">
      <div className="mb-2 text-xs font-medium text-text-primary">Rules for {role.name}</div>
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-border-subtle">
            <th className="pb-1 pr-4 text-2xs font-medium text-text-tertiary">API Groups</th>
            <th className="pb-1 pr-4 text-2xs font-medium text-text-tertiary">Resources</th>
            <th className="pb-1 pr-4 text-2xs font-medium text-text-tertiary">Verbs</th>
            <th className="pb-1 text-2xs font-medium text-text-tertiary">Resource Names</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {role.rules.map((rule, i) => (
            <tr key={`${rule.apiGroups.join(',')}-${rule.resources.join(',')}-${rule.verbs.join(',')}-${i}`}>
              <td className="py-1.5 pr-4 font-mono text-text-secondary">
                {rule.apiGroups.map((g) => g || '""').join(', ')}
              </td>
              <td className="py-1.5 pr-4 font-mono text-text-secondary">
                {rule.resources.join(', ')}
              </td>
              <td className="py-1.5 pr-4">
                <div className="flex flex-wrap gap-1">
                  {rule.verbs.map((v) => (
                    <span
                      key={v}
                      className={`rounded px-1.5 py-0.5 text-2xs font-medium ${
                        v === '*'
                          ? 'bg-warning-muted text-warning'
                          : ['create', 'update', 'patch', 'delete', 'deletecollection'].includes(v)
                            ? 'bg-error-muted text-error'
                            : 'bg-success-muted text-success'
                      }`}
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </td>
              <td className="py-1.5 font-mono text-text-tertiary">
                {rule.resourceNames.length > 0 ? rule.resourceNames.join(', ') : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div>
      <ErrorAlert message={error} />

      <div className="mb-4 flex items-center justify-between">
        <div className="flex gap-1 overflow-x-auto rounded-md bg-surface-2 p-0.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setExpandedRule(null); }}
              className={`whitespace-nowrap rounded px-3 py-1.5 text-xs font-medium transition-all ${
                tab === t.key
                  ? 'bg-surface-1 text-text-primary shadow-sm'
                  : 'text-text-tertiary hover:text-text-secondary'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {isNamespaced && (
          <NamespaceSelector value={namespace} onChange={setNamespace} />
        )}
      </div>

      {loading ? (
        <LoadingState message={`Loading ${tab}...`} />
      ) : (
        <>
          {(tab === 'roles' || tab === 'clusterroles') && (
            <>
              <ResourceTable
                columns={roleColumns}
                data={items.filter(isRole)}
                keyFn={(r) => `${r.namespace}/${r.name}`}
                emptyMessage={`No ${tab} found`}
              />
              {expandedRule && (
                <>
                  {items.filter(isRole)
                    .filter((r) => r.name === expandedRule)
                    .map((r) => (
                      <div key={r.name}>{renderExpandedRules(r)}</div>
                    ))}
                </>
              )}
            </>
          )}

          {(tab === 'bindings' || tab === 'clusterrolebindings') && (
            <ResourceTable
              columns={bindingColumns}
              data={items.filter(isRoleBinding)}
              keyFn={(b) => `${b.namespace}/${b.name}`}
              emptyMessage={`No ${tab} found`}
            />
          )}

          {tab === 'serviceaccounts' && (
            <ResourceTable
              columns={saColumns}
              data={items.filter(isServiceAccount)}
              keyFn={(sa) => `${sa.namespace}/${sa.name}`}
              emptyMessage="No service accounts found"
            />
          )}
        </>
      )}
    </div>
  );
}
