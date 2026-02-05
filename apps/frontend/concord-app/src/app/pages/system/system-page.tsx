import { NavLink, Outlet, Navigate } from 'react-router-dom';
import { Activity, HardDrive, Box, Layers, Network, Clock, FileText, Shield, Bell } from 'lucide-react';
import { useAuth } from '../../auth-provider';
import { PageHeader } from '../../components/ui/page-header';

const tabs = [
  { to: '/system', label: 'Overview', icon: Activity, end: true },
  { to: '/system/nodes', label: 'Nodes', icon: HardDrive },
  { to: '/system/pods', label: 'Pods', icon: Box },
  { to: '/system/deployments', label: 'Deployments', icon: Layers },
  { to: '/system/services', label: 'Services', icon: Network },
  { to: '/system/jobs', label: 'Jobs', icon: Clock },
  { to: '/system/config', label: 'Config', icon: FileText },
  { to: '/system/rbac', label: 'RBAC', icon: Shield },
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
      <div className="mb-6 flex gap-1 overflow-x-auto rounded-lg bg-surface-2 p-0.5">
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
