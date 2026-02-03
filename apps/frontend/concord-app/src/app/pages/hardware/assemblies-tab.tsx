import { useCallback, useEffect, useState } from 'react';
import { Plus, X, Check } from 'lucide-react';
import { api, apiUpload } from '../../api';
import { useAuth } from '../../auth-provider';
import { AssemblyCard } from './assembly-card';
import { ImageUpload } from './image-upload';
import { BomEditor } from './bom-editor';

interface BomItem {
  id: string;
  hardwareRevisionId: string;
  quantity: number;
  hardwareRevision?: {
    id: string;
    version: string;
    status: string;
    componentId: string;
    component?: {
      id: string;
      name: string;
      category: string;
      manufacturer: string;
      partNumber: string;
    };
  };
}

interface AssemblyRevision {
  id: string;
  assemblyId: string;
  version: string;
  status: string;
  releaseNotes: string | null;
  bom?: BomItem[];
  createdAt: string;
  updatedAt: string;
}

interface Assembly {
  id: string;
  name: string;
  description: string | null;
  imageKey: string | null;
  imageUrl: string | null;
  revisionCount: number;
  revisions?: AssemblyRevision[];
  createdAt: string;
  updatedAt: string;
}

interface HardwareRevisionOption {
  id: string;
  version: string;
  status: string;
  componentId: string;
  componentName: string;
  category: string;
}

interface ComponentData {
  id: string;
  name: string;
  category: string;
  revisions?: {
    id: string;
    version: string;
    status: string;
    componentId: string;
  }[];
}

interface ApiResponse<T> {
  data: T;
}

export function AssembliesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('Concord.Admin.Hardware.Manage');

  const [assemblies, setAssemblies] = useState<Assembly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [availableRevisions, setAvailableRevisions] = useState<HardwareRevisionOption[]>([]);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');

  // Detail view
  const [selectedAssembly, setSelectedAssembly] = useState<Assembly | null>(null);

  // Revision form
  const [showRevForm, setShowRevForm] = useState(false);
  const [revVersion, setRevVersion] = useState('');
  const [revStatus, setRevStatus] = useState('ACTIVE');
  const [revNotes, setRevNotes] = useState('');
  const [revBom, setRevBom] = useState<{ hardwareRevisionId: string; quantity: number }[]>([]);

  const fetchAssemblies = useCallback(async () => {
    try {
      const res = await api<ApiResponse<Assembly[]>>('/v2/hardware/assemblies');
      setAssemblies(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load assemblies');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAvailableRevisions = useCallback(async () => {
    try {
      const res = await api<ApiResponse<ComponentData[]>>('/v2/hardware/components');
      const revisions: HardwareRevisionOption[] = [];
      for (const comp of res.data) {
        for (const rev of comp.revisions || []) {
          revisions.push({
            id: rev.id,
            version: rev.version,
            status: rev.status,
            componentId: comp.id,
            componentName: comp.name,
            category: comp.category,
          });
        }
      }
      setAvailableRevisions(revisions);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchAssemblies();
    fetchAvailableRevisions();
  }, [fetchAssemblies, fetchAvailableRevisions]);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      const res = await api<ApiResponse<Assembly>>(`/v2/hardware/assemblies/${id}`);
      setSelectedAssembly(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load assembly');
    }
  }, []);

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setEditingId(null);
    setShowForm(false);
  };

  const startEdit = (a: Assembly) => {
    setFormName(a.name);
    setFormDescription(a.description || '');
    setEditingId(a.id);
    setShowForm(true);
    setSelectedAssembly(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const body = {
      name: formName,
      description: formDescription || null,
    };

    try {
      if (editingId) {
        await api(`/v2/hardware/assemblies/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      } else {
        await api('/v2/hardware/assemblies', {
          method: 'POST',
          body: JSON.stringify(body),
        });
      }
      resetForm();
      fetchAssemblies();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save assembly');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this assembly and all its revisions?')) return;
    setError(null);
    try {
      await api(`/v2/hardware/assemblies/${id}`, { method: 'DELETE' });
      if (selectedAssembly?.id === id) setSelectedAssembly(null);
      fetchAssemblies();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const handleImageUpload = async (assemblyId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    await apiUpload(`/v2/hardware/assemblies/${assemblyId}/image`, formData);
    fetchAssemblies();
    if (selectedAssembly?.id === assemblyId) fetchDetail(assemblyId);
  };

  const handleCreateRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAssembly) return;
    setError(null);
    try {
      await api(`/v2/hardware/assemblies/${selectedAssembly.id}/revisions`, {
        method: 'POST',
        body: JSON.stringify({
          version: revVersion,
          status: revStatus,
          releaseNotes: revNotes || null,
          bom: revBom,
        }),
      });
      setRevVersion('');
      setRevStatus('ACTIVE');
      setRevNotes('');
      setRevBom([]);
      setShowRevForm(false);
      fetchDetail(selectedAssembly.id);
      fetchAssemblies();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create revision');
    }
  };

  const handleDeleteRevision = async (revisionId: string) => {
    if (!selectedAssembly) return;
    try {
      await api(
        `/v2/hardware/assemblies/${selectedAssembly.id}/revisions/${revisionId}`,
        { method: 'DELETE' }
      );
      fetchDetail(selectedAssembly.id);
      fetchAssemblies();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete revision');
    }
  };

  if (loading) {
    return (
      <div className="py-12 text-center text-sm text-text-tertiary">
        Loading assemblies...
      </div>
    );
  }

  // Detail view
  if (selectedAssembly) {
    return (
      <div className="animate-fade-in">
        <button
          onClick={() => setSelectedAssembly(null)}
          className="mb-4 text-sm text-accent hover:underline"
        >
          &larr; Back to assemblies
        </button>

        <div className="rounded-xl border border-border bg-surface-1 p-5">
          <div className="flex gap-6">
            <div className="w-48 shrink-0">
              <ImageUpload
                currentUrl={selectedAssembly.imageUrl}
                onUpload={(file) => handleImageUpload(selectedAssembly.id, file)}
                disabled={!canManage}
              />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-text-primary">
                {selectedAssembly.name}
              </h2>
              {selectedAssembly.description && (
                <p className="mt-1 text-sm text-text-secondary">
                  {selectedAssembly.description}
                </p>
              )}
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
                <div className="mb-3 grid grid-cols-3 gap-3">
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

                <BomEditor
                  bom={revBom}
                  onChange={setRevBom}
                  availableRevisions={availableRevisions}
                />

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
                    onClick={() => {
                      setShowRevForm(false);
                      setRevBom([]);
                    }}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}

            {selectedAssembly.revisions && selectedAssembly.revisions.length > 0 ? (
              <div className="space-y-3">
                {selectedAssembly.revisions.map((rev) => (
                  <div
                    key={rev.id}
                    className="rounded-lg border border-border bg-surface-0 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-text-primary">
                          {rev.version}
                        </span>
                        <span
                          className={[
                            'rounded-full px-2 py-0.5 text-2xs font-medium',
                            rev.status === 'ACTIVE'
                              ? 'bg-success-muted text-success'
                              : rev.status === 'DEPRECATED'
                                ? 'bg-warning-muted text-warning'
                                : 'bg-error-muted text-error',
                          ].join(' ')}
                        >
                          {rev.status}
                        </span>
                        {rev.releaseNotes && (
                          <span className="text-2xs text-text-tertiary">
                            {rev.releaseNotes}
                          </span>
                        )}
                      </div>
                      {canManage && (
                        <button
                          onClick={() => handleDeleteRevision(rev.id)}
                          className="rounded px-2 py-1 text-2xs text-error hover:bg-error-muted"
                        >
                          Delete
                        </button>
                      )}
                    </div>

                    {/* BOM */}
                    {rev.bom && rev.bom.length > 0 && (
                      <div className="mt-2 border-t border-border-subtle pt-2">
                        <div className="mb-1 text-2xs font-medium text-text-tertiary">
                          Bill of Materials
                        </div>
                        <div className="space-y-0.5">
                          {rev.bom.map((item) => (
                            <div
                              key={item.id}
                              className="text-2xs text-text-secondary"
                            >
                              {item.quantity}x{' '}
                              {item.hardwareRevision?.component?.name || 'Unknown'}{' '}
                              <span className="text-text-tertiary">
                                ({item.hardwareRevision?.version || '?'})
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
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
      {error && (
        <div className="mb-4 rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
          {error}
        </div>
      )}

      {showForm && canManage && (
        <div className="mb-6 rounded-xl border border-border bg-surface-1 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              {editingId ? 'Edit assembly' : 'New assembly'}
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
                  placeholder="e.g. MTIB Assembly"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
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
            New assembly
          </button>
        </div>
      )}

      {assemblies.length === 0 ? (
        <div className="py-12 text-center text-sm text-text-tertiary">
          No assemblies yet
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assemblies.map((a) => (
            <AssemblyCard
              key={a.id}
              assembly={a}
              canManage={canManage}
              onEdit={startEdit}
              onDelete={handleDelete}
              onSelect={(asm) => fetchDetail(asm.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
