import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { UserPlus, Shield, Eye, Wrench, X, Check } from 'lucide-react';
import { useAuth, User } from '../auth-provider';
import { api } from '../api';
import { PageHeader } from '../components/ui/page-header';

const ROLE_ICON = {
  ADMIN: Shield,
  OPERATOR: Wrench,
  VIEWER: Eye,
} as const;

const ROLE_LABEL = {
  ADMIN: 'Admin',
  OPERATOR: 'Operator',
  VIEWER: 'Viewer',
} as const;

interface FullUser extends User {
  active: boolean;
  lastSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<FullUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formEmail, setFormEmail] = useState('');
  const [formName, setFormName] = useState('');
  const [formRole, setFormRole] = useState<'ADMIN' | 'OPERATOR' | 'VIEWER'>(
    'VIEWER'
  );

  const fetchUsers = useCallback(async () => {
    try {
      const data = await api<{ users: FullUser[] }>('/v2/auth/users');
      setUsers(data.users);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  if (currentUser?.role !== 'ADMIN') {
    return <Navigate to="/" replace />;
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api('/v2/auth/users', {
        method: 'POST',
        body: JSON.stringify({
          email: formEmail,
          name: formName,
          role: formRole,
        }),
      });
      setFormEmail('');
      setFormName('');
      setFormRole('VIEWER');
      setShowCreate(false);
      fetchUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
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

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      await api(`/v2/auth/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify({ role }),
      });
      fetchUsers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update role');
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return 'Never';
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="Users"
          description="Manage who can access Concord."
          actions={
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover"
            >
              {showCreate ? <X size={16} /> : <UserPlus size={16} />}
              {showCreate ? 'Cancel' : 'Add user'}
            </button>
          }
        />
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
          {error}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
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
                Role
              </label>
              <div className="flex gap-2">
                <select
                  value={formRole}
                  onChange={(e) =>
                    setFormRole(
                      e.target.value as 'ADMIN' | 'OPERATOR' | 'VIEWER'
                    )
                  }
                  className="flex-1 rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
                >
                  <option value="VIEWER">Viewer</option>
                  <option value="OPERATOR">Operator</option>
                  <option value="ADMIN">Admin</option>
                </select>
                <button
                  type="submit"
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover"
                >
                  <Check size={16} />
                </button>
              </div>
            </div>
          </div>
        </form>
      )}

      {/* Users table */}
      {loading ? (
        <div className="py-12 text-center text-sm text-text-tertiary">
          Loading users...
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-1">
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  User
                </th>
                <th className="px-4 py-3 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Role
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
                const RoleIcon = ROLE_ICON[u.role];
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
                      {isSelf ? (
                        <span className="inline-flex items-center gap-1.5 text-text-secondary">
                          <RoleIcon size={14} />
                          {ROLE_LABEL[u.role]}
                        </span>
                      ) : (
                        <select
                          value={u.role}
                          onChange={(e) =>
                            handleRoleChange(u.id, e.target.value)
                          }
                          className="rounded border border-border bg-surface-0 px-2 py-1 text-sm text-text-primary focus:border-accent focus:outline-none"
                        >
                          <option value="VIEWER">Viewer</option>
                          <option value="OPERATOR">Operator</option>
                          <option value="ADMIN">Admin</option>
                        </select>
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
                      {!isSelf && (
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
