import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Plus, X, Pencil, Trash2, Check } from 'lucide-react';
import { useAuth } from '../auth-provider';
import { api } from '../api';
import { PageHeader } from '../components/ui/page-header';

interface AvailablePermission {
  key: string;
  name: string;
}

interface PermissionSet {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  userCount: number;
  createdAt: string;
  updatedAt: string;
}

// Group permissions by their category prefix for the checkbox UI
function groupPermissions(permissions: AvailablePermission[]) {
  const groups: Record<string, AvailablePermission[]> = {};
  for (const p of permissions) {
    // e.g. "Concord.Firmware.AppID.Create" → "Firmware"
    const parts = p.key.split('.');
    const group = parts.length >= 3 ? parts[1] : 'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push(p);
  }
  return groups;
}

export function PermissionSetsPage() {
  const { hasPermission } = useAuth();
  const [sets, setSets] = useState<PermissionSet[]>([]);
  const [availablePerms, setAvailablePerms] = useState<AvailablePermission[]>(
    [],
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formPermissions, setFormPermissions] = useState<Set<string>>(
    new Set(),
  );

  const fetchSets = useCallback(async () => {
    try {
      const data = await api<{ data: PermissionSet[] }>(
        '/v2/auth/permission-sets',
      );
      setSets(data.data);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to load permission sets',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPermissions = useCallback(async () => {
    try {
      const data = await api<{ data: AvailablePermission[] }>(
        '/v2/auth/permissions',
      );
      setAvailablePerms(data.data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchSets();
    fetchPermissions();
  }, [fetchSets, fetchPermissions]);

  if (!hasPermission('Concord.Admin.PermissionSets.View')) {
    return <Navigate to="/" replace />;
  }

  const canManage = hasPermission('Concord.Admin.PermissionSets.Manage');
  const permGroups = groupPermissions(availablePerms);

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormPermissions(new Set());
    setEditingId(null);
    setShowForm(false);
  };

  const startEdit = (ps: PermissionSet) => {
    setFormName(ps.name);
    setFormDescription(ps.description || '');
    setFormPermissions(new Set(ps.permissions));
    setEditingId(ps.id);
    setShowForm(true);
  };

  const togglePermission = (key: string) => {
    setFormPermissions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const toggleGroup = (groupPerms: AvailablePermission[]) => {
    setFormPermissions((prev) => {
      const next = new Set(prev);
      const allSelected = groupPerms.every((p) => next.has(p.key));
      for (const p of groupPerms) {
        if (allSelected) {
          next.delete(p.key);
        } else {
          next.add(p.key);
        }
      }
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const body = {
      name: formName,
      description: formDescription || null,
      permissions: Array.from(formPermissions),
    };

    try {
      if (editingId) {
        await api(`/v2/auth/permission-sets/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      } else {
        await api('/v2/auth/permission-sets', {
          method: 'POST',
          body: JSON.stringify(body),
        });
      }
      resetForm();
      fetchSets();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to save permission set',
      );
    }
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await api(`/v2/auth/permission-sets/${id}`, { method: 'DELETE' });
      fetchSets();
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to delete permission set',
      );
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="Permission Sets"
          description="Define groups of permissions and assign them to users."
          actions={
            canManage && !showForm ? (
              <button
                onClick={() => {
                  resetForm();
                  setShowForm(true);
                }}
                className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover"
              >
                <Plus size={16} />
                New set
              </button>
            ) : undefined
          }
        />
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
          {error}
        </div>
      )}

      {/* Create/Edit form */}
      {showForm && canManage && (
        <div className="mb-6 rounded-xl border border-border bg-surface-1 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              {editingId ? 'Edit permission set' : 'New permission set'}
            </h3>
            <button
              onClick={resetForm}
              className="rounded-lg p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
            >
              <X size={16} />
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="mb-4 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Name
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Technician"
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

            {/* Permissions checkboxes */}
            <div className="mb-4">
              <label className="mb-2 block text-2xs font-medium text-text-tertiary">
                Permissions
              </label>
              <div className="rounded-lg border border-border bg-surface-0 p-4">
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(permGroups).map(([group, perms]) => {
                    const allChecked = perms.every((p) =>
                      formPermissions.has(p.key),
                    );
                    const someChecked = perms.some((p) =>
                      formPermissions.has(p.key),
                    );
                    return (
                      <div key={group}>
                        <label className="mb-1.5 flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={allChecked}
                            ref={(el) => {
                              if (el)
                                el.indeterminate = someChecked && !allChecked;
                            }}
                            onChange={() => toggleGroup(perms)}
                            className="rounded border-border text-accent focus:ring-accent"
                          />
                          <span className="text-xs font-semibold text-text-primary">
                            {group}
                          </span>
                        </label>
                        <div className="ml-5 space-y-1">
                          {perms.map((p) => {
                            // Extract the last part as a readable label
                            const parts = p.key.split('.');
                            const label = parts[parts.length - 1];
                            return (
                              <label
                                key={p.key}
                                className="flex items-center gap-2"
                              >
                                <input
                                  type="checkbox"
                                  checked={formPermissions.has(p.key)}
                                  onChange={() => togglePermission(p.key)}
                                  className="rounded border-border text-accent focus:ring-accent"
                                />
                                <span className="text-2xs text-text-secondary">
                                  {label}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={formPermissions.size === 0}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover disabled:opacity-50"
              >
                <Check size={14} />
                {editingId ? 'Save changes' : 'Create'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Permission sets list */}
      {loading ? (
        <div className="py-12 text-center text-sm text-text-tertiary">
          Loading permission sets...
        </div>
      ) : (
        <div className="space-y-3">
          {sets.map((ps) => (
            <div
              key={ps.id}
              className="rounded-xl border border-border bg-surface-1 p-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-text-primary">
                    {ps.name}
                  </h4>
                  {ps.description && (
                    <p className="mt-0.5 text-2xs text-text-tertiary">
                      {ps.description}
                    </p>
                  )}
                  <div className="mt-2 flex items-center gap-3 text-2xs text-text-tertiary">
                    <span>
                      {ps.permissions.length} permission
                      {ps.permissions.length !== 1 ? 's' : ''}
                    </span>
                    <span>
                      {ps.userCount} user{ps.userCount !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
                {canManage && (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEdit(ps)}
                      className="rounded-lg p-2 text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
                      title="Edit"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(ps.id)}
                      className="rounded-lg p-2 text-text-tertiary transition-colors hover:bg-error-muted hover:text-error"
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>

              {/* Permissions chips */}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {ps.permissions.map((perm) => {
                  const parts = perm.split('.');
                  const short = parts.slice(1).join('.');
                  return (
                    <span
                      key={perm}
                      className="rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-text-secondary"
                    >
                      {short}
                    </span>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
