# Phase 4 — Frontend: System Page Layout, Shared Components, Routing, Nav

## Objective

Create the system page shell with sub-navigation, build all shared components used across Tier 1–3, wire up the route in app.tsx, and add the sidebar nav item.

---

## 1. Create `src/app/components/system/metric-card.tsx`

A small stat card displaying a number, label, and optional icon. Used on the overview and node detail pages.

```tsx
import { type LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  subtitle?: string;
  status?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
}

export function MetricCard({ label, value, icon: Icon, subtitle, status = 'neutral' }: MetricCardProps) {
  const statusColors: Record<string, string> = {
    success: 'text-success',
    warning: 'text-warning',
    error: 'text-error',
    info: 'text-info',
    neutral: 'text-text-primary',
  };

  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
          {label}
        </span>
        {Icon && <Icon size={14} className="text-text-tertiary" />}
      </div>
      <div className={`mt-1 text-2xl font-semibold ${statusColors[status]}`}>
        {value}
      </div>
      {subtitle && (
        <div className="mt-0.5 text-xs text-text-tertiary">{subtitle}</div>
      )}
    </div>
  );
}
```

---

## 2. Create `src/app/components/system/status-indicator.tsx`

A dot + label for K8s statuses (Ready, NotReady, Running, Pending, Failed, etc.).

```tsx
const STATUS_MAP: Record<string, { color: string; bg: string }> = {
  Ready: { color: 'bg-success', bg: 'bg-success-muted' },
  Running: { color: 'bg-success', bg: 'bg-success-muted' },
  Active: { color: 'bg-success', bg: 'bg-success-muted' },
  Succeeded: { color: 'bg-success', bg: 'bg-success-muted' },
  Pending: { color: 'bg-warning', bg: 'bg-warning-muted' },
  NotReady: { color: 'bg-error', bg: 'bg-error-muted' },
  Failed: { color: 'bg-error', bg: 'bg-error-muted' },
  Error: { color: 'bg-error', bg: 'bg-error-muted' },
  Unknown: { color: 'bg-text-tertiary', bg: 'bg-surface-2' },
  Warning: { color: 'bg-warning', bg: 'bg-warning-muted' },
  Normal: { color: 'bg-success', bg: 'bg-success-muted' },
};

export function StatusIndicator({ status }: { status: string }) {
  const style = STATUS_MAP[status] || STATUS_MAP.Unknown;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${style.bg}`}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${style.color}`} />
      {status}
    </span>
  );
}
```

---

## 3. Create `src/app/components/system/resource-age.tsx`

Displays a relative time string. Used in tables.

```tsx
export function ResourceAge({ timestamp }: { timestamp: string | null }) {
  if (!timestamp) return <span className="text-text-tertiary">-</span>;

  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  let display: string;
  if (diffMins < 1) display = '<1m';
  else if (diffMins < 60) display = `${diffMins}m`;
  else if (diffHours < 24) display = `${diffHours}h`;
  else display = `${diffDays}d`;

  return (
    <span className="text-text-secondary" title={date.toLocaleString()}>
      {display}
    </span>
  );
}
```

---

## 4. Create `src/app/components/system/namespace-selector.tsx`

Dropdown to pick a namespace. "All namespaces" is the default.

```tsx
import { useEffect, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';

interface Namespace {
  name: string;
  status: string;
}

interface NamespaceSelectorProps {
  value: string;
  onChange: (ns: string) => void;
}

export function NamespaceSelector({ value, onChange }: NamespaceSelectorProps) {
  const [namespaces, setNamespaces] = useState<Namespace[]>([]);

  useEffect(() => {
    api<ApiResponse<Namespace[]>>('/v2/system/namespaces')
      .then((res) => setNamespaces(res.data))
      .catch(() => {});
  }, []);

  return (
    <div className="relative inline-block">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-md border border-border bg-surface-1 py-1.5 pl-3 pr-8 text-xs text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-focus-ring"
      >
        <option value="">All namespaces</option>
        {namespaces.map((ns) => (
          <option key={ns.name} value={ns.name}>
            {ns.name}
          </option>
        ))}
      </select>
      <ChevronDown size={12} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
    </div>
  );
}
```

---

## 5. Create `src/app/components/system/resource-table.tsx`

A generic table component used across all system pages.

```tsx
import { type ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
  className?: string;
}

interface ResourceTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (item: T) => string;
  onRowClick?: (item: T) => void;
  emptyMessage?: string;
}

export function ResourceTable<T>({
  columns,
  data,
  keyFn,
  onRowClick,
  emptyMessage = 'No resources found',
}: ResourceTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-text-tertiary">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-3 py-2 text-2xs font-medium uppercase tracking-wide text-text-tertiary ${col.className || ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {data.map((item) => (
            <tr
              key={keyFn(item)}
              className={`bg-surface-1 transition-colors ${
                onRowClick ? 'cursor-pointer hover:bg-surface-2' : ''
              }`}
              onClick={() => onRowClick?.(item)}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-3 py-2 ${col.className || ''}`}>
                  {col.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 6. Create `src/app/pages/system/system-page.tsx`

The layout shell with sub-navigation tabs. Uses `<Outlet />` for nested routes.

```tsx
import { NavLink, Outlet, Navigate } from 'react-router-dom';
import { Activity, HardDrive, Bell } from 'lucide-react';
import { useAuth } from '../../auth-provider';
import { PageHeader } from '../../components/ui/page-header';

const tabs = [
  { to: '/system', label: 'Overview', icon: Activity, end: true },
  { to: '/system/nodes', label: 'Nodes', icon: HardDrive },
  { to: '/system/events', label: 'Events', icon: Bell },
];

export function SystemPage() {
  const { hasPermission } = useAuth();

  if (!hasPermission('Concord.Admin.System.View')) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="System"
          description="Kubernetes cluster overview and operational monitoring."
        />
      </div>

      {/* Sub-navigation */}
      <div className="mb-6 flex gap-1 rounded-lg bg-surface-2 p-0.5">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              [
                'flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-all',
                isActive
                  ? 'bg-surface-1 text-text-primary shadow-sm'
                  : 'text-text-tertiary hover:text-text-secondary',
              ].join(' ')
            }
          >
            <tab.icon size={14} />
            {tab.label}
          </NavLink>
        ))}
      </div>

      <Outlet />
    </div>
  );
}
```

---

## 7. Modify `src/app/app.tsx`

Add imports and nested routes for the system page.

**Import** (add with the other page imports):

```tsx
import { SystemPage } from './pages/system/system-page';
import { SystemOverview } from './pages/system/overview';
import { NodesList } from './pages/system/nodes-list';
import { NodeDetail } from './pages/system/node-detail';
import { EventsList } from './pages/system/events-list';
```

**Routes** (add inside the `<Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>` block, after the other admin routes):

```tsx
<Route path="system" element={<SystemPage />}>
  <Route index element={<SystemOverview />} />
  <Route path="nodes" element={<NodesList />} />
  <Route path="nodes/:nodeName" element={<NodeDetail />} />
  <Route path="events" element={<EventsList />} />
</Route>
```

Create placeholder components for `overview.tsx`, `nodes-list.tsx`, `node-detail.tsx`, `events-list.tsx` — each exports a component that renders `<div>Coming soon</div>`. These get implemented in Phases 5 and 6.

---

## 8. Modify `src/app/components/sidebar.tsx`

Add the System nav item to the admin section.

**Import** `Monitor` icon from lucide-react (add to existing icon imports).

**Add nav item** inside the admin section, before the Hardware link:

```tsx
{hasPermission('Concord.Admin.System.View') && (
  <SidebarLink to="/system" icon={Monitor} label="System" collapsed={collapsed} onDoubleClick={onToggle} />
)}
```

Also update the `isAdmin` check to include the new permission:

```tsx
const isAdmin = hasPermission('Concord.Admin.Users.View') ||
               hasPermission('Concord.Admin.Hardware.View') ||
               hasPermission('Concord.Admin.Codebases.View') ||
               hasPermission('Concord.Admin.History.View') ||
               hasPermission('Concord.Admin.System.View');
```

---

## Verification

1. Frontend compiles: `npx nx build concord-app` (or dev server shows no errors)
2. Navigate to `/system` — see the page layout with 3 tabs
3. Sidebar shows "System" under Admin section
4. Tab navigation works between Overview/Nodes/Events (all showing placeholder content)
5. Users without `Concord.Admin.System.View` permission are redirected from `/system`

---

## Overview Update

```
- [x] Phase 4 — Frontend: system page layout, shared components, routing, nav
```
