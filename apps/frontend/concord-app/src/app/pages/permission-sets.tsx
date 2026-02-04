import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Plus,
  X,
  Pencil,
  Trash2,
  Check,
  ChevronRight,
  ChevronDown,
} from 'lucide-react';
import { useAuth } from '../auth-provider';
import { api } from '../api';
import { PageHeader } from '../components/ui/page-header';
import { ConfirmDeleteDialog } from '../components/ui/confirm-delete-dialog';
import { ErrorAlert } from '../components/ui/error-alert';
import { LoadingState } from '../components/ui/loading-state';

interface AvailablePermission {
  key: string;
  name: string;
}

interface PermissionSetUser {
  id: string;
  name: string;
  email: string;
}

interface PermissionSet {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  userCount: number;
  users: PermissionSetUser[];
  createdAt: string;
  updatedAt: string;
}

// ── Action color mapping ──────────────────────────────────────

const ACTION_COLORS: Record<
  string,
  { bg: string; text: string; dot: string }
> = {
  Create: {
    bg: 'bg-success-muted',
    text: 'text-success',
    dot: 'bg-success',
  },
  View: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
  Read: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
  Update: {
    bg: 'bg-warning-muted',
    text: 'text-warning',
    dot: 'bg-warning',
  },
  Delete: {
    bg: 'bg-error-muted',
    text: 'text-error',
    dot: 'bg-error',
  },
  Manage: {
    bg: 'bg-accent-muted',
    text: 'text-accent',
    dot: 'bg-accent',
  },
  Run: {
    bg: 'bg-accent-muted',
    text: 'text-accent',
    dot: 'bg-accent',
  },
};

const DEFAULT_COLOR = {
  bg: 'bg-surface-2',
  text: 'text-text-secondary',
  dot: 'bg-text-tertiary',
};

function getActionColor(action: string) {
  return ACTION_COLORS[action] || DEFAULT_COLOR;
}

// ── Tree data structure ───────────────────────────────────────

interface TreeNode {
  label: string;
  permKey?: string; // set only on leaf nodes (the full permission key)
  children: TreeNode[];
}

/** Build a nested tree from flat permission keys like "Concord.Firmware.AppID.Create" */
function buildTree(permissions: AvailablePermission[]): TreeNode[] {
  const root: TreeNode = { label: 'root', children: [] };

  for (const p of permissions) {
    // Skip the "Concord" prefix — start from index 1
    const parts = p.key.split('.');
    const segments = parts.slice(1); // ["Firmware", "AppID", "Create"]

    let current = root;
    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];
      const isLeaf = i === segments.length - 1;

      let child = current.children.find((c) => c.label === seg);
      if (!child) {
        child = {
          label: seg,
          children: [],
          ...(isLeaf ? { permKey: p.key } : {}),
        };
        current.children.push(child);
      }
      if (isLeaf) {
        child.permKey = p.key;
      }
      current = child;
    }
  }

  return root.children;
}

/** Collect all permission keys under a tree node */
function collectKeys(node: TreeNode): string[] {
  if (node.permKey) return [node.permKey];
  return node.children.flatMap(collectKeys);
}

// ── Tree checkbox component (for form) ────────────────────────

function TreeCheckboxNode({
  node,
  selectedPerms,
  onToggle,
  onToggleAll,
  depth,
}: {
  node: TreeNode;
  selectedPerms: Set<string>;
  onToggle: (key: string) => void;
  onToggleAll: (keys: string[], selected: boolean) => void;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(true);
  const isLeaf = !!node.permKey;
  const allKeys = collectKeys(node);
  const checkedCount = allKeys.filter((k) => selectedPerms.has(k)).length;
  const allChecked = checkedCount === allKeys.length;
  const someChecked = checkedCount > 0 && !allChecked;

  if (isLeaf) {
    const color = getActionColor(node.label);
    return (
      <label
        className="flex items-center gap-2.5 py-0.5 cursor-pointer group"
        style={{ paddingLeft: `${depth * 20}px` }}
      >
        <input
          type="checkbox"
          checked={selectedPerms.has(node.permKey!)}
          onChange={() => onToggle(node.permKey!)}
          className="rounded border-border text-accent focus:ring-accent"
        />
        <span
          className={[
            'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-2xs font-medium transition-opacity',
            color.bg,
            color.text,
            selectedPerms.has(node.permKey!)
              ? 'opacity-100'
              : 'opacity-50',
          ].join(' ')}
        >
          <span className={['h-1.5 w-1.5 rounded-full', color.dot].join(' ')} />
          {node.label}
        </span>
      </label>
    );
  }

  return (
    <div>
      <div
        className="flex items-center gap-1 py-1 cursor-pointer select-none"
        style={{ paddingLeft: `${depth * 20}px` }}
      >
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex h-5 w-5 items-center justify-center rounded text-text-tertiary hover:text-text-primary"
        >
          {expanded ? (
            <ChevronDown size={14} strokeWidth={2} />
          ) : (
            <ChevronRight size={14} strokeWidth={2} />
          )}
        </button>
        <input
          type="checkbox"
          checked={allChecked}
          ref={(el) => {
            if (el) el.indeterminate = someChecked;
          }}
          onChange={() => onToggleAll(allKeys, !allChecked)}
          className="rounded border-border text-accent focus:ring-accent"
        />
        <span className="text-xs font-semibold text-text-primary">
          {node.label}
        </span>
        <span className="text-2xs text-text-tertiary ml-1">
          {checkedCount}/{allKeys.length}
        </span>
      </div>
      {expanded && (
        <div>
          {node.children.map((child) => (
            <TreeCheckboxNode
              key={child.label}
              node={child}
              selectedPerms={selectedPerms}
              onToggle={onToggle}
              onToggleAll={onToggleAll}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Read-only tree display (for list cards) ───────────────────

function TreeDisplayNode({
  node,
  enabledPerms,
  depth,
}: {
  node: TreeNode;
  enabledPerms: Set<string>;
  depth: number;
}) {
  const isLeaf = !!node.permKey;

  if (isLeaf) {
    const enabled = enabledPerms.has(node.permKey!);
    const color = getActionColor(node.label);
    return (
      <span
        className={[
          'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-2xs font-medium',
          enabled ? color.bg : 'bg-transparent',
          enabled ? color.text : 'text-text-tertiary line-through opacity-40',
        ].join(' ')}
      >
        <span
          className={[
            'h-1.5 w-1.5 rounded-full',
            enabled ? color.dot : 'bg-text-tertiary opacity-40',
          ].join(' ')}
        />
        {node.label}
      </span>
    );
  }

  const childKeys = collectKeys(node);
  const enabledCount = childKeys.filter((k) => enabledPerms.has(k)).length;

  // Collect leaf actions for this node
  const leafChildren = node.children.filter((c) => c.permKey);
  const branchChildren = node.children.filter((c) => !c.permKey);

  return (
    <div style={{ paddingLeft: depth > 0 ? '16px' : '0' }}>
      <div className="flex items-center gap-2 py-1">
        <span
          className={[
            'text-2xs font-semibold',
            enabledCount > 0 ? 'text-text-primary' : 'text-text-tertiary opacity-60',
          ].join(' ')}
        >
          {node.label}
        </span>
        {/* Render leaf actions inline */}
        {leafChildren.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {leafChildren.map((child) => (
              <TreeDisplayNode
                key={child.label}
                node={child}
                enabledPerms={enabledPerms}
                depth={0}
              />
            ))}
          </div>
        )}
      </div>
      {/* Render branch children below */}
      {branchChildren.map((child) => (
        <TreeDisplayNode
          key={child.label}
          node={child}
          enabledPerms={enabledPerms}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

// ── Collapsible permission set card ───────────────────────────

function PermissionSetCard({
  ps,
  tree,
  canManage,
  onEdit,
  onDelete,
}: {
  ps: PermissionSet;
  tree: TreeNode[];
  canManage: boolean;
  onEdit: (ps: PermissionSet) => void;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const enabledPerms = new Set(ps.permissions);
  const allKeys = tree.flatMap(collectKeys);
  const totalCount = allKeys.length;

  return (
    <div className="rounded-xl border border-border bg-surface-1">
      {/* Header — always visible, clickable to toggle */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left"
      >
        <div className="flex h-5 w-5 shrink-0 items-center justify-center text-text-tertiary">
          {expanded ? (
            <ChevronDown size={16} strokeWidth={2} />
          ) : (
            <ChevronRight size={16} strokeWidth={2} />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-text-primary">
              {ps.name}
            </h4>
            <span className="rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
              {ps.permissions.length}/{totalCount}
            </span>
          </div>
          {ps.description && (
            <p className="mt-0.5 text-2xs text-text-tertiary">
              {ps.description}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {ps.users.length > 0 ? (
            <div className="flex items-center gap-1.5">
              <div className="flex -space-x-1.5">
                {ps.users.slice(0, 5).map((u) => (
                  <div
                    key={u.id}
                    title={`${u.name} (${u.email})`}
                    className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface-1 bg-accent-muted text-2xs font-semibold text-accent"
                  >
                    {u.name.charAt(0).toUpperCase()}
                  </div>
                ))}
                {ps.users.length > 5 && (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface-1 bg-surface-2 text-2xs font-medium text-text-tertiary">
                    +{ps.users.length - 5}
                  </div>
                )}
              </div>
              <span className="text-2xs text-text-tertiary">
                {ps.userCount} user{ps.userCount !== 1 ? 's' : ''}
              </span>
            </div>
          ) : (
            <span className="text-2xs text-text-tertiary">No users</span>
          )}
          {canManage && (
            <div
              className="flex items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => onEdit(ps)}
                className="rounded-lg p-2 text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
                title="Edit"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => onDelete(ps.id)}
                className="rounded-lg p-2 text-text-tertiary transition-colors hover:bg-error-muted hover:text-error"
                title="Delete"
              >
                <Trash2 size={14} />
              </button>
            </div>
          )}
        </div>
      </button>

      {/* Collapsible body */}
      {expanded && (
        <div className="border-t border-border-subtle">
          {/* Users list */}
          {ps.users.length > 0 && (
            <div className="border-b border-border-subtle px-4 py-3">
              <div className="mb-2 text-2xs font-medium text-text-tertiary">
                Assigned users
              </div>
              <div className="flex flex-wrap gap-2">
                {ps.users.map((u) => (
                  <div
                    key={u.id}
                    className="flex items-center gap-2 rounded-lg bg-surface-2 px-2.5 py-1.5"
                  >
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-muted text-2xs font-semibold text-accent">
                      {u.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-2xs font-medium text-text-primary">
                        {u.name}
                      </div>
                      <div className="text-2xs text-text-tertiary">
                        {u.email}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Permissions tree */}
          <div className="px-4 py-3">
            {tree.map((node) => (
              <TreeDisplayNode
                key={node.label}
                node={node}
                enabledPerms={enabledPerms}
                depth={0}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main page component ───────────────────────────────────────

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
  const [deleteTarget, setDeleteTarget] = useState<{id: string, name: string} | null>(null);

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
  const tree = buildTree(availablePerms);

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
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleAll = (keys: string[], selected: boolean) => {
    setFormPermissions((prev) => {
      const next = new Set(prev);
      for (const k of keys) {
        if (selected) next.add(k);
        else next.delete(k);
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

  const doDelete = async (id: string) => {
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

  const handleDelete = (id: string) => {
    const target = sets.find(s => s.id === id);
    setDeleteTarget({ id, name: target?.name || '' });
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
                className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
              >
                <Plus size={16} />
                New set
              </button>
            ) : undefined
          }
        />
      </div>

      <ErrorAlert message={error} />

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

            {/* Permissions tree */}
            <div className="mb-4">
              <label className="mb-2 block text-2xs font-medium text-text-tertiary">
                Permissions
              </label>
              <div className="rounded-lg border border-border bg-surface-0 p-3">
                {tree.map((node) => (
                  <TreeCheckboxNode
                    key={node.label}
                    node={node}
                    selectedPerms={formPermissions}
                    onToggle={togglePermission}
                    onToggleAll={toggleAll}
                    depth={0}
                  />
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={formPermissions.size === 0}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
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
        <LoadingState message="Loading permission sets..." />
      ) : (
        <div className="space-y-3">
          {sets.map((ps) => (
            <PermissionSetCard
              key={ps.id}
              ps={ps}
              tree={tree}
              canManage={canManage}
              onEdit={startEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="permission set"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { doDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
