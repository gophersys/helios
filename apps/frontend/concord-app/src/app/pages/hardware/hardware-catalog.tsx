import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../auth-provider';
import { PageHeader } from '../../components/ui/page-header';
import { ComponentsTab } from './components-tab';
import { AssembliesTab } from './assemblies-tab';

type Tab = 'components' | 'assemblies';

export function HardwareCatalogPage() {
  const { hasPermission } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('components');

  if (!hasPermission('Concord.Admin.Hardware.View')) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="Hardware Catalog"
          description="Manage hardware components, assemblies, and their revisions."
        />
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-lg bg-surface-2 p-0.5">
        <button
          onClick={() => setActiveTab('components')}
          className={[
            'flex-1 rounded-md px-4 py-2 text-sm font-medium transition-all',
            activeTab === 'components'
              ? 'bg-surface-1 text-text-primary shadow-sm'
              : 'text-text-tertiary hover:text-text-secondary',
          ].join(' ')}
        >
          Components
        </button>
        <button
          onClick={() => setActiveTab('assemblies')}
          className={[
            'flex-1 rounded-md px-4 py-2 text-sm font-medium transition-all',
            activeTab === 'assemblies'
              ? 'bg-surface-1 text-text-primary shadow-sm'
              : 'text-text-tertiary hover:text-text-secondary',
          ].join(' ')}
        >
          Assemblies
        </button>
      </div>

      {activeTab === 'components' ? <ComponentsTab /> : <AssembliesTab />}
    </div>
  );
}
