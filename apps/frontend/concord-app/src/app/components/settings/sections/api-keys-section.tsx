import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2, Copy, Check } from 'lucide-react';
import { api } from '../../../api';
import { ConfirmDeleteDialog } from '../../ui/confirm-delete-dialog';
import { ErrorAlert } from '../../ui/error-alert';
import { formatDate } from '../../../utils/formatting';

interface ApiKey {
  id: string;
  name: string;
  keyPrefix: string;
  expiresAt: string | null;
  lastUsedAt: string | null;
  createdAt: string;
}

export function ApiKeysSection() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{id: string, name: string} | null>(null);

  const [formName, setFormName] = useState('');
  const [formExpiresAt, setFormExpiresAt] = useState('');

  const fetchKeys = useCallback(async () => {
    try {
      const data = await api<{ data: ApiKey[] }>('/v2/auth/api-keys');
      setKeys(data.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load API keys');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const body: Record<string, string> = { name: formName };
      if (formExpiresAt) {
        body.expiresAt = new Date(formExpiresAt).toISOString();
      }
      const data = await api<{ data: { key: string } & ApiKey }>(
        '/v2/auth/api-keys',
        {
          method: 'POST',
          body: JSON.stringify(body),
        },
      );
      setNewKey(data.data.key);
      setFormName('');
      setFormExpiresAt('');
      setShowCreate(false);
      fetchKeys();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create API key');
    }
  };

  const handleDelete = (keyId: string) => {
    const target = keys.find(k => k.id === keyId);
    setDeleteTarget({ id: keyId, name: target?.name || '' });
  };

  const doDelete = async (keyId: string) => {
    try {
      await api(`/v2/auth/api-keys/${keyId}`, { method: 'DELETE' });
      fetchKeys();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete API key');
    }
  };

  const handleCopy = async (key: string) => {
    await navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <p className="mb-4 text-sm text-text-secondary">
        Create API keys to authenticate programmatic access to Concord. Keys
        inherit your permissions.
      </p>

      <ErrorAlert message={error} />

      {/* New key display */}
      {newKey && (
        <div className="mb-4 rounded-lg border border-success bg-success-muted p-4">
          <p className="mb-2 text-sm font-medium text-success">
            API key created. Copy it now — you won't see it again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-surface-0 px-3 py-2 text-xs font-mono text-text-primary break-all">
              {newKey}
            </code>
            <button
              onClick={() => handleCopy(newKey)}
              className="shrink-0 rounded-lg border border-border bg-surface-0 p-2 text-text-secondary transition-colors hover:bg-surface-1"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
          <button
            onClick={() => setNewKey(null)}
            className="mt-2 text-2xs text-text-tertiary hover:text-text-secondary"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Create button */}
      <div className="mb-4">
        {showCreate ? (
          <form
            onSubmit={handleCreate}
            className="rounded-lg border border-border bg-surface-1 p-4"
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Key name
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. CI Pipeline"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Expires (optional)
                </label>
                <input
                  type="date"
                  value={formExpiresAt}
                  onChange={(e) => setFormExpiresAt(e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
                />
              </div>
            </div>
            <div className="mt-3 flex gap-2">
              <button
                type="submit"
                className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-surface-0 transition-colors hover:bg-accent-hover"
              >
                Create key
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-2"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-1"
          >
            <Plus size={14} />
            Create API key
          </button>
        )}
      </div>

      {/* Keys list */}
      {loading ? (
        <div className="py-8 text-center text-sm text-text-tertiary">
          Loading API keys...
        </div>
      ) : keys.length === 0 ? (
        <div className="py-8 text-center text-sm text-text-tertiary">
          No API keys yet.
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((k) => (
            <div
              key={k.id}
              className="flex items-center justify-between rounded-lg border border-border-subtle px-4 py-3"
            >
              <div>
                <div className="text-sm font-medium text-text-primary">
                  {k.name}
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-2xs text-text-tertiary">
                  <code className="font-mono">{k.keyPrefix}...</code>
                  <span>Created {formatDate(k.createdAt)}</span>
                  {k.expiresAt && <span>Expires {formatDate(k.expiresAt)}</span>}
                  {k.lastUsedAt && (
                    <span>Last used {formatDate(k.lastUsedAt)}</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleDelete(k.id)}
                className="shrink-0 rounded-lg p-2 text-text-tertiary transition-colors hover:bg-error-muted hover:text-error"
                title="Delete key"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="API key"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { doDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
