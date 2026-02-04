import { useCallback, useEffect, useState } from 'react';
import { Plus, X, Check } from 'lucide-react';
import { api, apiUpload } from '../../api';
import { useAuth } from '../../auth-provider';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { StatusBadge } from '../../components/ui/status-badge';
import { ErrorAlert } from '../../components/ui/error-alert';
import { EmptyState } from '../../components/ui/empty-state';
import { LoadingState } from '../../components/ui/loading-state';
import { ApiResponse } from '../../types';
import { ComponentCard } from './component-card';
import { ImageUpload } from './image-upload';

interface Revision {
  id: string;
  componentId: string;
  version: string;
  status: string;
  releaseNotes: string | null;
  createdAt: string;
  updatedAt: string;
}

interface Component {
  id: string;
  name: string;
  description: string | null;
  category: string;
  manufacturer: string;
  partNumber: string;
  imageKey: string | null;
  imageUrl: string | null;
  revisionCount: number;
  revisions?: Revision[];
  createdAt: string;
  updatedAt: string;
}

export function ComponentsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('Concord.Admin.Hardware.Manage');

  const [components, setComponents] = useState<Component[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formCategory, setFormCategory] = useState('SOM');
  const [formManufacturer, setFormManufacturer] = useState('');
  const [formPartNumber, setFormPartNumber] = useState('');

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<{id: string, name: string} | null>(null);
  const [deleteRevTarget, setDeleteRevTarget] = useState<{id: string, name: string} | null>(null);

  // Detail / revision state
  const [selectedComponent, setSelectedComponent] = useState<Component | null>(null);
  const [revVersion, setRevVersion] = useState('');
  const [revStatus, setRevStatus] = useState('ACTIVE');
  const [revNotes, setRevNotes] = useState('');
  const [showRevForm, setShowRevForm] = useState(false);

  const fetchComponents = useCallback(async () => {
    try {
      const res = await api<ApiResponse<Component[]>>('/v2/hardware/components');
      setComponents(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load components');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchComponents();
  }, [fetchComponents]);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      const res = await api<ApiResponse<Component>>(`/v2/hardware/components/${id}`);
      setSelectedComponent(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load component');
    }
  }, []);

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormCategory('SOM');
    setFormManufacturer('');
    setFormPartNumber('');
    setEditingId(null);
    setShowForm(false);
  };

  const startEdit = (c: Component) => {
    setFormName(c.name);
    setFormDescription(c.description || '');
    setFormCategory(c.category);
    setFormManufacturer(c.manufacturer);
    setFormPartNumber(c.partNumber);
    setEditingId(c.id);
    setShowForm(true);
    setSelectedComponent(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const body = {
      name: formName,
      description: formDescription || null,
      category: formCategory,
      manufacturer: formManufacturer,
      partNumber: formPartNumber,
    };

    try {
      if (editingId) {
        await api(`/v2/hardware/components/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      } else {
        await api('/v2/hardware/components', {
          method: 'POST',
          body: JSON.stringify(body),
        });
      }
      resetForm();
      fetchComponents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save component');
    }
  };

  const handleDelete = (id: string) => {
    const target = components.find(c => c.id === id);
    setDeleteTarget({ id, name: target?.name || '' });
  };

  const doDelete = async (id: string) => {
    setError(null);
    try {
      await api(`/v2/hardware/components/${id}`, { method: 'DELETE' });
      if (selectedComponent?.id === id) setSelectedComponent(null);
      fetchComponents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const handleImageUpload = async (componentId: string, file: File) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      await apiUpload(`/v2/hardware/components/${componentId}/image`, formData);
      fetchComponents();
      if (selectedComponent?.id === componentId) fetchDetail(componentId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to upload image');
    }
  };

  const handleCreateRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedComponent) return;
    setError(null);
    try {
      await api(`/v2/hardware/components/${selectedComponent.id}/revisions`, {
        method: 'POST',
        body: JSON.stringify({
          version: revVersion,
          status: revStatus,
          releaseNotes: revNotes || null,
        }),
      });
      setRevVersion('');
      setRevStatus('ACTIVE');
      setRevNotes('');
      setShowRevForm(false);
      fetchDetail(selectedComponent.id);
      fetchComponents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create revision');
    }
  };

  const handleDeleteRevision = (revisionId: string) => {
    if (!selectedComponent) return;
    const rev = selectedComponent.revisions?.find((r: any) => r.id === revisionId);
    setDeleteRevTarget({ id: revisionId, name: rev?.version || '' });
  };

  const doDeleteRevision = async (revisionId: string) => {
    if (!selectedComponent) return;
    try {
      await api(
        `/v2/hardware/components/${selectedComponent.id}/revisions/${revisionId}`,
        { method: 'DELETE' }
      );
      fetchDetail(selectedComponent.id);
      fetchComponents();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete revision');
    }
  };

  if (loading) {
    return <LoadingState message="Loading components..." />;
  }

  // Detail view
  if (selectedComponent) {
    return (
      <div className="animate-fade-in">
        <button
          onClick={() => setSelectedComponent(null)}
          className="mb-4 text-sm text-accent hover:underline"
        >
          &larr; Back to components
        </button>

        <div className="rounded-xl border border-border bg-surface-1 p-5">
          <div className="flex gap-6">
            {/* Image */}
            <div className="w-48 shrink-0">
              <ImageUpload
                currentUrl={selectedComponent.imageUrl}
                onUpload={(file) => handleImageUpload(selectedComponent.id, file)}
                disabled={!canManage}
              />
            </div>

            {/* Info */}
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-text-primary">
                {selectedComponent.name}
              </h2>
              {selectedComponent.description && (
                <p className="mt-1 text-sm text-text-secondary">
                  {selectedComponent.description}
                </p>
              )}
              <div className="mt-3 flex gap-4 text-2xs text-text-tertiary">
                <span>
                  <strong className="text-text-secondary">Category:</strong>{' '}
                  {selectedComponent.category === 'CARRIER_BOARD'
                    ? 'Carrier Board'
                    : selectedComponent.category === 'SOM'
                      ? 'SoM'
                      : 'Accessory'}
                </span>
                <span>
                  <strong className="text-text-secondary">Manufacturer:</strong>{' '}
                  {selectedComponent.manufacturer}
                </span>
                <span>
                  <strong className="text-text-secondary">Part #:</strong>{' '}
                  {selectedComponent.partNumber}
                </span>
              </div>
            </div>
          </div>

          {/* Revisions */}
          <div className="mt-6">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary">Revisions</h3>
              {canManage && !showRevForm && (
                <button
                  onClick={() => setShowRevForm(true)}
                  className="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
                >
                  <Plus size={13} />
                  Add revision
                </button>
              )}
            </div>

            {showRevForm && (
              <form
                onSubmit={handleCreateRevision}
                className="mb-4 rounded-lg border border-border bg-surface-0 p-3"
              >
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                      Version
                    </label>
                    <input
                      type="text"
                      required
                      value={revVersion}
                      onChange={(e) => setRevVersion(e.target.value)}
                      placeholder="e.g. REV1.0"
                      className="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                      Status
                    </label>
                    <select
                      value={revStatus}
                      onChange={(e) => setRevStatus(e.target.value)}
                      className="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
                    >
                      <option value="ACTIVE">Active</option>
                      <option value="DEPRECATED">Deprecated</option>
                      <option value="EOL">End of Life</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                      Release Notes
                    </label>
                    <input
                      type="text"
                      value={revNotes}
                      onChange={(e) => setRevNotes(e.target.value)}
                      placeholder="Optional"
                      className="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                    />
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    type="submit"
                    className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
                  >
                    <Check size={13} />
                    Create
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRevForm(false)}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            {selectedComponent.revisions && selectedComponent.revisions.length > 0 ? (
              <div className="overflow-hidden rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-surface-2">
                      <th className="px-3 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                        Version
                      </th>
                      <th className="px-3 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                        Status
                      </th>
                      <th className="px-3 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                        Notes
                      </th>
                      {canManage && (
                        <th className="px-3 py-2 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                          Actions
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {selectedComponent.revisions.map((rev) => (
                      <tr
                        key={rev.id}
                        className="border-b border-border-subtle last:border-0 hover:bg-surface-1"
                      >
                        <td className="px-3 py-2 font-medium text-text-primary">
                          {rev.version}
                        </td>
                        <td className="px-3 py-2">
                          <StatusBadge status={rev.status} />
                        </td>
                        <td className="px-3 py-2 text-text-secondary">
                          {rev.releaseNotes || '-'}
                        </td>
                        {canManage && (
                          <td className="px-3 py-2 text-right">
                            <button
                              onClick={() => handleDeleteRevision(rev.id)}
                              className="rounded px-2 py-1 text-2xs text-error hover:bg-error-muted"
                            >
                              Delete
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-text-tertiary">
                No revisions yet
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <ErrorAlert message={error} />

      {/* Create/Edit form */}
      {showForm && canManage && (
        <div className="mb-6 rounded-xl border border-border bg-surface-1 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              {editingId ? 'Edit component' : 'New component'}
            </h3>
            <button
              onClick={resetForm}
              className="rounded-lg p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
            >
              <X size={16} />
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="mb-3 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Name
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Verdin iMX8MM"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Category
                </label>
                <select
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
                >
                  <option value="SOM">SoM</option>
                  <option value="CARRIER_BOARD">Carrier Board</option>
                  <option value="ACCESSORY">Accessory</option>
                </select>
              </div>
            </div>
            <div className="mb-3 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Manufacturer
                </label>
                <input
                  type="text"
                  required
                  value={formManufacturer}
                  onChange={(e) => setFormManufacturer(e.target.value)}
                  placeholder="e.g. Toradex"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Part Number
                </label>
                <input
                  type="text"
                  required
                  value={formPartNumber}
                  onChange={(e) => setFormPartNumber(e.target.value)}
                  placeholder="e.g. 0074"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                Description
              </label>
              <input
                type="text"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Optional description"
                className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
              >
                <Check size={14} />
                {editingId ? 'Save changes' : 'Create'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Add button */}
      {canManage && !showForm && (
        <div className="mb-4 flex justify-end">
          <button
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            New component
          </button>
        </div>
      )}

      {/* Grid */}
      {components.length === 0 ? (
        <EmptyState message="No hardware components yet" />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {components.map((c) => (
            <ComponentCard
              key={c.id}
              component={c}
              canManage={canManage}
              onEdit={startEdit}
              onDelete={handleDelete}
              onSelect={(comp) => fetchDetail(comp.id)}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="component"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { doDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
      <ConfirmDeleteDialog
        open={!!deleteRevTarget}
        entityType="revision"
        entityName={deleteRevTarget?.name || ''}
        onConfirm={() => { doDeleteRevision(deleteRevTarget!.id); setDeleteRevTarget(null); }}
        onCancel={() => setDeleteRevTarget(null)}
      />
    </div>
  );
}
