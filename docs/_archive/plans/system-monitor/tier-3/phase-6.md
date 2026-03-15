# Phase 6 — Frontend: RBAC Viewer + Final Polish

## Objective

Build the RBAC viewer page and apply final polish across all system pages. This completes Tier 3 and the full system monitor.

---

## 1. Modify `src/app/pages/system/system-page.tsx`

Add the RBAC tab.

**Update icon imports:**

```tsx
import { Activity, HardDrive, Bell, Box, Layers, Globe, Briefcase, FileText, Shield } from 'lucide-react';
```

**Add tab entry** (insert before Events):

```tsx
{ to: '/system/rbac', label: 'RBAC', icon: Shield },
```

The full tabs array should now be:

```tsx
const tabs = [
  { to: '/system', label: 'Overview', icon: Activity, end: true },
  { to: '/system/nodes', label: 'Nodes', icon: HardDrive },
  { to: '/system/pods', label: 'Pods', icon: Box },
  { to: '/system/deployments', label: 'Deployments', icon: Layers },
  { to: '/system/services', label: 'Services', icon: Globe },
  { to: '/system/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/system/config', label: 'Config', icon: FileText },
  { to: '/system/rbac', label: 'RBAC', icon: Shield },
  { to: '/system/events', label: 'Events', icon: Bell },
];
```

---

## 2. Modify `src/app/app.tsx`

**Add import:**

```tsx
import { RbacPage } from './pages/system/rbac';
```

**Add route** inside the `<Route path="system">` block:

```tsx
<Route path="rbac" element={<RbacPage />} />
```

---

## 3. Create `src/app/pages/system/rbac.tsx`

```tsx
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { ErrorAlert } from '../../components/ui/error-alert';
import { LoadingState } from '../../components/ui/loading-state';
import { NamespaceSelector } from '../../components/system/namespace-selector';
import { ResourceTable, type Column } from '../../components/system/resource-table';
import { ResourceAge } from '../../components/system/resource-age';

type RbacTab = 'roles' | 'clusterroles' | 'bindings' | 'clusterrolebindings' | 'serviceaccounts';

interface Role {
  name: string;
  namespace: string;
  rules: { apiGroups: string[]; resources: string[]; verbs: string[]; resourceNames: string[] }[];
  createdAt: string;
}

interface RoleBinding {
  name: string;
  namespace: string;
  roleRef: { kind: string; name: string };
  subjects: { kind: string; name: string; namespace: string }[];
  createdAt: string;
}

interface ServiceAccount {
  name: string;
  namespace: string;
  secrets: string[];
  createdAt: string;
}

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

export function RbacPage() {
  const [tab, setTab] = useState<RbacTab>('roles');
  const [namespace, setNamespace] = useState('');
  const [data, setData] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  const currentTabConfig = TABS.find((t) => t.key === tab)!;

  const fetchData = useCallback(async () => {
    const params = new URLSearchParams();
    if (namespace && currentTabConfig.namespaced) {
      params.set('namespace', namespace);
    }

    try {
      const res = await api<ApiResponse<unknown[]>>(`${API_PATHS[tab]}?${params}`);
      setData(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to load ${tab}`);
    } finally {
      setLoading(false);
    }
  }, [tab, namespace]);

  useEffect(() => {
    setLoading(true);
    setExpandedRule(null);
    fetchData();
  }, [fetchData]);

  // Role columns
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
      render: (r) => <span className="text-text-secondary">{r.rules.length} rule{r.rules.length !== 1 ? 's' : ''}</span>,
    },
    {
      key: 'age',
      header: 'Age',
      render: (r) => <ResourceAge timestamp={r.createdAt} />,
    },
  ];

  // Binding columns
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
            <span key={i} className="rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
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

  // ServiceAccount columns
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
            <tr key={i}>
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
                          ? 'bg-warning/20 text-warning'
                          : ['create', 'update', 'patch', 'delete', 'deletecollection'].includes(v)
                          ? 'bg-error/10 text-error'
                          : 'bg-success/10 text-success'
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

      {/* Tab bar */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex gap-1 overflow-x-auto rounded-md bg-surface-2 p-0.5">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
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

        {currentTabConfig.namespaced && (
          <NamespaceSelector value={namespace} onChange={setNamespace} />
        )}
      </div>

      {/* Content */}
      {loading ? (
        <LoadingState message={`Loading ${tab}...`} />
      ) : (
        <>
          {(tab === 'roles' || tab === 'clusterroles') && (
            <>
              <ResourceTable
                columns={roleColumns}
                data={data as Role[]}
                keyFn={(r) => `${(r as Role).namespace}/${(r as Role).name}`}
                emptyMessage={`No ${tab} found`}
              />
              {expandedRule && (
                <>
                  {(data as Role[])
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
              data={data as RoleBinding[]}
              keyFn={(b) => `${(b as RoleBinding).namespace}/${(b as RoleBinding).name}`}
              emptyMessage={`No ${tab} found`}
            />
          )}

          {tab === 'serviceaccounts' && (
            <ResourceTable
              columns={saColumns}
              data={data as ServiceAccount[]}
              keyFn={(sa) => `${(sa as ServiceAccount).namespace}/${(sa as ServiceAccount).name}`}
              emptyMessage="No service accounts found"
            />
          )}
        </>
      )}
    </div>
  );
}
```

---

## 4. Final polish checklist

Apply these small improvements across all existing system pages:

### 4a. Add keyboard shortcut for YAML dialog

In `resource-yaml-dialog.tsx`, add Escape key to close:

```tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
  };
  if (open) {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }
}, [open, onClose]);
```

### 4b. Prevent body scroll when modal is open

In `resource-yaml-dialog.tsx`:

```tsx
useEffect(() => {
  if (open) {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }
}, [open]);
```

### 4c. Add error boundary

If a system page crashes due to unexpected K8s data, the whole app shouldn't break. This is optional but recommended — wrap the `<Outlet />` in `system-page.tsx` with a simple error boundary that catches render errors and shows a message.

---

## Verification

1. Frontend compiles without errors
2. RBAC tab appears in system navigation
3. `/system/rbac` — shows Roles tab by default with namespace filter
4. Clicking a role name expands to show rules with verb color coding
5. ClusterRoles tab hides namespace selector
6. RoleBindings show subjects and role references
7. ServiceAccounts show secrets count
8. Pod exec terminal works end-to-end (exec, type commands, see output)
9. YAML dialog works on all detail pages
10. All pages work in light and dark mode

---

## Overview Update

Mark all phases complete:

```
- [x] Phase 1 — Backend: generic resource YAML get/apply service
- [x] Phase 2 — Backend: RBAC service module
- [x] Phase 3 — Backend: API routes for resources + RBAC, pod exec SocketIO
- [x] Phase 4 — Frontend: YAML viewer/editor components + resource YAML dialog
- [x] Phase 5 — Frontend: terminal component + pod exec integration
- [x] Phase 6 — Frontend: RBAC viewer page + final polish
```

**Tier 3 is complete.** The system monitor now has full k9s-like capabilities: resource browser, log streaming, pod exec, YAML editing, and RBAC viewing.
