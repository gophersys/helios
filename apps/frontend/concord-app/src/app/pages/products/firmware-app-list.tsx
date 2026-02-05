import { useState } from 'react';
import { Plus, X, Check, ChevronDown, ChevronRight, Pencil, Trash2, Cpu } from 'lucide-react';
import { api } from '../../api';
import { Select } from '../../components/ui/select';
import { ErrorAlert } from '../../components/ui/error-alert';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { ApiResponse } from '../../types';
import { FirmwareBuildList } from './firmware-build-list';
import { type ChipsetConfig, FirmwareApp, FirmwareBuild, BoardRevision } from '../../types/models';

/** Group firmware apps by chipset. Apps with no chipset go into "Unassigned". */
function groupByChipset(apps: FirmwareApp[]): { chipset: string; apps: FirmwareApp[] }[] {
  const groups = new Map<string, FirmwareApp[]>();
  for (const app of apps) {
    const key = app.chipset || 'Unassigned';
    const list = groups.get(key) || [];
    list.push(app);
    groups.set(key, list);
  }
  // Sort groups: named chipsets alphabetically first, "Unassigned" last
  const entries = [...groups.entries()].sort((a, b) => {
    if (a[0] === 'Unassigned') return 1;
    if (b[0] === 'Unassigned') return -1;
    return a[0].localeCompare(b[0]);
  });
  return entries.map(([chipset, apps]) => ({ chipset, apps }));
}

export function FirmwareAppList({
  productId,
  apps,
  builds,
  boardRevisions,
  chipsetConfig,
  canManage,
  onRefresh,
}: {
  productId: string;
  apps: FirmwareApp[];
  builds: FirmwareBuild[];
  boardRevisions: BoardRevision[];
  chipsetConfig: ChipsetConfig | null;
  canManage: boolean;
  onRefresh: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [expandedApps, setExpandedApps] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  // Form fields
  const [formAppId, setFormAppId] = useState('');
  const [formName, setFormName] = useState('');
  const [formTargetMcu, setFormTargetMcu] = useState('');
  const [formChipset, setFormChipset] = useState('');
  const [formCloudDeviceType, setFormCloudDeviceType] = useState('');
  const [formCloudVariant, setFormCloudVariant] = useState('');
  const [formNotes, setFormNotes] = useState('');

  // Available chipset names and their target MCUs from backend config
  const chipsetNames = chipsetConfig?.chipsets.map((c) => c.name) || [];
  const getTargetMcus = (chipset: string) =>
    chipsetConfig?.chipsets.find((c) => c.name === chipset)?.targetMcus || [];

  const resetForm = () => {
    setFormAppId('');
    setFormName('');
    setFormTargetMcu('');
    setFormChipset('');
    setFormCloudDeviceType('');
    setFormCloudVariant('');
    setFormNotes('');
    setEditingId(null);
    setShowForm(false);
  };

  const startEdit = (a: FirmwareApp) => {
    setFormAppId(String(a.applicationId));
    setFormName(a.name);
    setFormTargetMcu(a.targetMcu || '');
    setFormChipset(a.chipset || '');
    setFormCloudDeviceType(a.coreCloudDeviceType || '');
    setFormCloudVariant(a.coreCloudVariant || '');
    setFormNotes(a.notes || '');
    setEditingId(a.id);
    setShowForm(true);
  };

  const toggleExpanded = (id: string) => {
    setExpandedApps((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body: Record<string, unknown> = {
      name: formName,
      targetMcu: formTargetMcu || null,
      chipset: formChipset || null,
      coreCloudDeviceType: formCloudDeviceType || null,
      coreCloudVariant: formCloudVariant || null,
      notes: formNotes || null,
    };

    if (!editingId) {
      body.applicationId = parseInt(formAppId, 10);
    }

    try {
      if (editingId) {
        await api(`/v2/products/${productId}/firmware-apps/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      } else {
        await api(`/v2/products/${productId}/firmware-apps`, {
          method: 'POST',
          body: JSON.stringify(body),
        });
      }
      resetForm();
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save firmware application');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await api(`/v2/products/${productId}/firmware-apps/${id}`, { method: 'DELETE' });
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const chipsetGroups = groupByChipset(apps);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">Firmware Applications</h3>
        {canManage && !showForm && (
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={13} />
            Add application
          </button>
        )}
      </div>

      <ErrorAlert message={error} />

      {showForm && (
        <div className="mb-4 rounded-lg border border-border bg-surface-0 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-2xs font-medium text-text-secondary">
              {editingId ? 'Edit application' : 'New application'}
            </span>
            <button onClick={resetForm} className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary">
              <X size={14} />
            </button>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="mb-3 grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">App ID</label>
                <input
                  type="number"
                  required
                  disabled={!!editingId}
                  value={formAppId}
                  onChange={(e) => setFormAppId(e.target.value)}
                  placeholder="e.g. 1"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none disabled:opacity-50"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Name</label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Main App"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Chipset</label>
                <Select
                  value={formChipset}
                  onChange={(e) => {
                    setFormChipset(e.target.value);
                    // Reset target MCU when chipset changes
                    const mcus = getTargetMcus(e.target.value);
                    if (formTargetMcu && !mcus.includes(formTargetMcu)) {
                      setFormTargetMcu('');
                    }
                  }}
                >
                  <option value="">Select chipset...</option>
                  {chipsetNames.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="mb-3 grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Target MCU</label>
                <Select
                  value={formTargetMcu}
                  onChange={(e) => setFormTargetMcu(e.target.value)}
                >
                  <option value="">Select target MCU...</option>
                  {(formChipset ? getTargetMcus(formChipset) : chipsetConfig?.supportedSocs || []).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Cloud Device Type</label>
                <input
                  type="text"
                  value={formCloudDeviceType}
                  onChange={(e) => setFormCloudDeviceType(e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Cloud Variant</label>
                <input
                  type="text"
                  value={formCloudVariant}
                  onChange={(e) => setFormCloudVariant(e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
            </div>
            <div className="mb-3">
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
              <input
                type="text"
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="Optional notes"
                className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={submitting} className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
                <Check size={12} />
                {submitting ? 'Saving...' : editingId ? 'Save' : 'Create'}
              </button>
              <button type="button" onClick={resetForm} className="rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {apps.length > 0 ? (
        <div className="space-y-4">
          {chipsetGroups.map(({ chipset, apps: groupApps }) => (
            <div key={chipset}>
              {/* Chipset group header */}
              <div className="mb-2 flex items-center gap-2">
                <Cpu size={14} className="text-accent" />
                <span className="text-xs font-semibold text-text-primary">{chipset}</span>
                <span className="text-2xs text-text-tertiary">
                  {groupApps.length} app{groupApps.length !== 1 ? 's' : ''}
                </span>
                <div className="flex-1 border-t border-border-subtle" />
              </div>

              <div className="space-y-2">
                {groupApps.map((app) => {
                  const isExpanded = expandedApps.has(app.id);
                  const appBuilds = builds.filter((b) => b.applicationId === app.id);
                  // Filter board revisions to those whose SoCs include this app's target MCU
                  const relevantBoardRevisions = app.targetMcu
                    ? boardRevisions.filter((r) => r.chipsets.includes(app.targetMcu!))
                    : boardRevisions;

                  return (
                    <div key={app.id} className="rounded-lg border border-border bg-surface-0">
                      <div
                        className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-surface-1"
                        onClick={() => toggleExpanded(app.id)}
                      >
                        {isExpanded ? (
                          <ChevronDown size={14} className="shrink-0 text-text-tertiary" />
                        ) : (
                          <ChevronRight size={14} className="shrink-0 text-text-tertiary" />
                        )}
                        <span className="rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono text-text-secondary">
                          ID {app.applicationId}
                        </span>
                        <span className="font-medium text-text-primary text-sm">{app.name}</span>
                        {app.targetMcu && (
                          <span className="rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary">
                            {app.targetMcu}
                          </span>
                        )}
                        <span className="ml-auto text-2xs text-text-tertiary">
                          {appBuilds.length} build{appBuilds.length !== 1 ? 's' : ''}
                        </span>

                        {canManage && (
                          <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => startEdit(app)}
                              className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                              title="Edit"
                              aria-label="Edit"
                            >
                              <Pencil size={13} />
                            </button>
                            <button
                              onClick={() => setDeleteTarget({ id: app.id, name: app.name })}
                              className="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                              title="Delete"
                              aria-label="Delete"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        )}
                      </div>

                      {isExpanded && app.notes && (
                        <div className="border-t border-border-subtle px-4 py-2 text-sm text-text-secondary">
                          {app.notes}
                        </div>
                      )}

                      {isExpanded && (
                        <div className="border-t border-border-subtle px-4 py-3">
                          <FirmwareBuildList
                            productId={productId}
                            applicationId={app.id}
                            builds={appBuilds}
                            boardRevisions={relevantBoardRevisions}
                            canManage={canManage}
                            onRefresh={onRefresh}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-6 text-center text-sm text-text-tertiary">
          No firmware applications yet
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="firmware application"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
