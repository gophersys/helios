import { useCallback, useEffect, useRef, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { UserPlus, X, Check } from 'lucide-react';
import { useAuth, User } from '../auth-provider';
import { api } from '../api';
import { PageHeader } from '../components/ui/page-header';
import { ErrorAlert } from '../components/ui/error-alert';
import { LoadingState } from '../components/ui/loading-state';
import { formatDate } from '../utils/formatting';
import { Select } from '../components/ui/select';
import { FullUser, PermissionSet } from '../types/models';

export function UsersPage() {
  const { user: currentUser, hasPermission } = useAuth();
  const [users, setUsers] = useState<FullUser[]>([]);
  const [permissionSets, setPermissionSets] = useState<PermissionSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formEmail, setFormEmail] = useState('');
  const [formName, setFormName] = useState('');
  const [formPermissionSetId, setFormPermissionSetId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const defaultSetApplied = useRef(false);

  const fetchUsers = useCallback(async () => {
    try {
      const data = await api<{ data: FullUser[]; errors: unknown[] }>('/v2/auth/users');
      setUsers(data.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPermissionSets = useCallback(async () => {
    try {
      const data = await api<{ data: PermissionSet[] }>('/v2/auth/permission-sets');
      setPermissionSets(data.data);
      // Set default selection only once
      if (data.data.length > 0 && !defaultSetApplied.current) {
        defaultSetApplied.current = true;
        const viewerSet = data.data.find((s) => s.name === 'Viewer');
        setFormPermissionSetId(viewerSet?.id || data.data[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load permission sets');
    }
  }, []);

  useEffect(() => {
    fetchUsers();
    fetchPermissionSets();
  }, [fetchUsers, fetchPermissionSets]);

  if (!hasPermission('Concord.Admin.Users.View')) {
    return <Navigate to="/" replace />;
  }

  const canManage = hasPermission('Concord.Admin.Users.Manage');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api('/v2/auth/users', {
        method: 'POST',
        body: JSON.stringify({
          email: formEmail,
          name: formName,
          permissionSetId: formPermissionSetId || null,
        }),
      });
      setFormEmail('');
      setFormName('');
      const viewerSet = permissionSets.find((s) => s.name === 'Viewer');
      setFormPermissionSetId(viewerSet?.id || permissionSets[0]?.id || '');
      setShowCreate(false);
      fetchUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean) => {
    try {
      await api(`/v2/auth/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify({ active: !currentActive }),
      });
      fetchUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update user');
    }
  };

  const handlePermissionSetChange = async (userId: string, permissionSetId: string) => {
    try {
      await api(`/v2/auth/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify({ permissionSetId: permissionSetId || null }),
      });
      fetchUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update permission set');
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="Users"
          description="Manage who can access Concord."
          actions={
            canManage ? (
              <button
                onClick={() => setShowCreate(!showCreate)}
                className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover"
              >
                {showCreate ? <X size={16} /> : <UserPlus size={16} />}
                {showCreate ? 'Cancel' : 'Add user'}
              </button>
            ) : undefined
          }
        />
      </div>

      <ErrorAlert message={error} />

      {/* Create form */}
      {showCreate && canManage && (
        <form
          onSubmit={handleCreate}
          className="mb-6 rounded-xl border border-border bg-surface-1 p-4"
        >
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                Email
              </label>
              <input
                type="email"
                required
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                placeholder="user@company.com"
                className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                Name
              </label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Full name"
                className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                Permission Set
              </label>
              <div className="flex gap-2">
                <Select
                  value={formPermissionSetId}
                  onChange={(e) => setFormPermissionSetId(e.target.value)}
                  className="flex-1"
                >
                  <option value="">None</option>
                  {permissionSets.map((ps) => (
                    <option key={ps.id} value={ps.id}>
                      {ps.name}
                    </option>
                  ))}
                </Select>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover disabled:opacity-50"
                >
                  {submitting ? '...' : <Check size={16} />}
                </button>
              </div>
            </div>
          </div>
        </form>
      )}

      {/* Users table */}
      {loading ? (
        <LoadingState message="Loading users..." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-1">
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  User
                </th>
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Permission Set
                </th>
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Last seen
                </th>
                <th className="px-4 py-3 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <tr
                    key={u.id}
                    className="border-b border-border-subtle last:border-0 hover:bg-surface-1"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-text-primary">
                        {u.name}
                        {isSelf && (
                          <span className="ml-2 text-2xs text-text-tertiary">
                            (you)
                          </span>
                        )}
                      </div>
                      <div className="text-2xs text-text-tertiary">
                        {u.email}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {isSelf || !canManage ? (
                        <span className="inline-flex items-center gap-1.5 text-text-secondary">
                          {u.permissionSetName || 'None'}
                        </span>
                      ) : (
                        <Select
                          compact
                          value={u.permissionSetId || ''}
                          onChange={(e) =>
                            handlePermissionSetChange(u.id, e.target.value)
                          }
                        >
                          <option value="">None</option>
                          {permissionSets.map((ps) => (
                            <option key={ps.id} value={ps.id}>
                              {ps.name}
                            </option>
                          ))}
                        </Select>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-2xs font-medium ${
                          u.active
                            ? 'bg-success-muted text-success'
                            : 'bg-error-muted text-error'
                        }`}
                      >
                        {u.active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {formatDate(u.lastSeenAt)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {!isSelf && canManage && (
                        <button
                          onClick={() => handleToggleActive(u.id, u.active)}
                          className={`rounded-lg px-3 py-1 text-2xs font-medium transition-colors ${
                            u.active
                              ? 'text-error hover:bg-error-muted'
                              : 'text-success hover:bg-success-muted'
                          }`}
                        >
                          {u.active ? 'Deactivate' : 'Activate'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
