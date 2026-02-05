import { useState } from 'react';
import { Cpu } from 'lucide-react';
import { BackButton } from '../../components/ui/back-button';
import { ErrorAlert } from '../../components/ui/error-alert';
import { useChipsetConfig } from '../../hooks/use-chipset-config';
import { BoardRevisionList } from './board-revision-list';
import { FirmwareAppList } from './firmware-app-list';
import { Product } from '../../types/models';

type Tab = 'overview' | 'firmware' | 'usage';

export function ProductDetail({
  product,
  canManage,
  onBack,
  onRefresh,
}: {
  product: Product;
  canManage: boolean;
  onBack: () => void;
  onRefresh: () => void;
}) {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [error, setError] = useState<string | null>(null);
  const { data: chipsetConfig } = useChipsetConfig();

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'firmware', label: 'Firmware' },
    { key: 'usage', label: 'Usage' },
  ];

  const boardRevisions = product.boardRevisions || [];
  const firmwareApps = product.firmwareApplications || [];
  const firmwareBuilds = product.firmwareBuilds || [];

  // Extract unique chipsets from firmware applications
  const chipsets = product.chipsets || [...new Set(firmwareApps.map((a) => a.chipset).filter(Boolean) as string[])].sort();

  return (
    <div className="animate-fade-in">
      <BackButton label="Back to products" onClick={onBack} />

      <ErrorAlert message={error} />

      <div className="rounded-xl border border-border bg-surface-1 p-5">
        {/* Header */}
        <div className="flex items-start gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-text-primary">
                {product.name}
              </h2>
              <span
                className={[
                  'inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium',
                  product.active
                    ? 'bg-success-muted text-success'
                    : 'bg-surface-2 text-text-tertiary',
                ].join(' ')}
              >
                {product.active ? 'Active' : 'Inactive'}
              </span>
            </div>
            {product.description && (
              <p className="mt-1 text-sm text-text-secondary">{product.description}</p>
            )}

            {/* Chipset badges */}
            {chipsets.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {chipsets.map((c) => (
                  <span
                    key={c}
                    className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent"
                  >
                    <Cpu size={12} />
                    {c}
                  </span>
                ))}
              </div>
            )}

            <div className="mt-3 flex gap-4 text-2xs text-text-tertiary">
              <span>
                <strong className="text-text-secondary">{boardRevisions.length}</strong> board revision{boardRevisions.length !== 1 ? 's' : ''}
              </span>
              <span>
                <strong className="text-text-secondary">{firmwareApps.length}</strong> firmware app{firmwareApps.length !== 1 ? 's' : ''}
              </span>
              <span>
                <strong className="text-text-secondary">{firmwareBuilds.length}</strong> firmware build{firmwareBuilds.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="mt-5 flex gap-1 border-b border-border">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={[
                'px-4 py-2 text-sm font-medium transition-colors',
                activeTab === tab.key
                  ? 'border-b-2 border-accent text-accent'
                  : 'text-text-tertiary hover:text-text-secondary',
              ].join(' ')}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="mt-5">
          {activeTab === 'overview' && (
            <BoardRevisionList
              productId={product.id}
              revisions={boardRevisions}
              supportedSocs={chipsetConfig?.supportedSocs || []}
              canManage={canManage}
              onRefresh={onRefresh}
            />
          )}

          {activeTab === 'firmware' && (
            <FirmwareAppList
              productId={product.id}
              apps={firmwareApps}
              builds={firmwareBuilds}
              boardRevisions={boardRevisions}
              chipsetConfig={chipsetConfig}
              canManage={canManage}
              onRefresh={onRefresh}
            />
          )}

          {activeTab === 'usage' && (
            <div className="py-8 text-center text-sm text-text-tertiary">
              Session and test usage statistics coming soon.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
