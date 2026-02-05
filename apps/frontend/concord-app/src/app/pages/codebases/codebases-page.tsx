import { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Plus, X, Check } from 'lucide-react';
import { api, apiUpload } from '../../api';
import { useAuth } from '../../auth-provider';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { ErrorAlert } from '../../components/ui/error-alert';
import { EmptyState } from '../../components/ui/empty-state';
import { LoadingState } from '../../components/ui/loading-state';
import { PageHeader } from '../../components/ui/page-header';
import { CodebaseCard } from './codebase-card';
import { ApiResponse } from '../../types';
import { CodebaseDetail } from './codebase-detail';
import { Codebase } from '../../types/models';

export function CodebasesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('Concord.Admin.Codebases.Manage');

  const [codebases, setCodebases] = useState<Codebase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formRepoUrl, setFormRepoUrl] = useState('');
  const [formDefaultBranch, setFormDefaultBranch] = useState('main');

  const [submitting, setSubmitting] = useState(false);

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<{id: string, name: string} | null>(null);

  // Detail state
  const [selectedCodebase, setSelectedCodebase] = useState<Codebase | null>(null);

  if (!hasPermission('Concord.Admin.Codebases.View')) {
    return <Navigate to="/" replace />;
  }

  const fetchCodebases = useCallback(async () => {
    try {
      const res = await api<ApiResponse<Codebase[]>>('/v2/codebases');
      setCodebases(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load codebases');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      const res = await api<ApiResponse<Codebase>>(`/v2/codebases/${id}`);
      setSelectedCodebase(res.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load codebase');
    }
  }, []);

  useEffect(() => {
    fetchCodebases();
  }, [fetchCodebases]);

  const resetForm = () => {
    setFormName('');
    setFormDescription('');
    setFormRepoUrl('');
    setFormDefaultBranch('main');
    setEditingId(null);
    setShowForm(false);
  };

  const startEdit = (c: Codebase) => {
    setFormName(c.name);
    setFormDescription(c.description || '');
    setFormRepoUrl(c.repoUrl || '');
    setFormDefaultBranch(c.defaultBranch);
    setEditingId(c.id);
    setShowForm(true);
    setSelectedCodebase(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body = {
      name: formName,
      description: formDescription || null,
      repoUrl: formRepoUrl || null,
      defaultBranch: formDefaultBranch,
    };

    try {
      if (editingId) {
        await api(`/v2/codebases/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      } else {
        await api('/v2/codebases', {
          method: 'POST',
          body: JSON.stringify(body),
        });
      }
      resetForm();
      fetchCodebases();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save codebase');
    } finally {
      setSubmitting(false);
    }
  };

  const promptDelete = (id: string) => {
    const target = codebases.find(c => c.id === id);
    setDeleteTarget({ id, name: target?.name || '' });
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await api(`/v2/codebases/${id}`, { method: 'DELETE' });
      if (selectedCodebase?.id === id) setSelectedCodebase(null);
      fetchCodebases();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const handleImageUpload = async (codebaseId: string, file: File) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      await apiUpload(`/v2/codebases/${codebaseId}/image`, formData);
      fetchCodebases();
      if (selectedCodebase?.id === codebaseId) fetchDetail(codebaseId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to upload image');
    }
  };

  if (loading) {
    return (
      <div className="animate-fade-in">
        <div className="mb-6">
          <PageHeader
            title="Codebases"
            description="Manage software repositories and their releases."
          />
        </div>
        <LoadingState message="Loading codebases..." />
      </div>
    );
  }

  // Detail view
  if (selectedCodebase) {
    return (
      <div className="animate-fade-in">
        <div className="mb-6">
          <PageHeader
            title="Codebases"
            description="Manage software repositories and their releases."
          />
        </div>
        <CodebaseDetail
          codebase={selectedCodebase}
          canManage={canManage}
          onBack={() => setSelectedCodebase(null)}
          onRefresh={() => fetchDetail(selectedCodebase.id)}
          onImageUpload={(file) => handleImageUpload(selectedCodebase.id, file)}
        />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <PageHeader
          title="Codebases"
          description="Manage software repositories and their releases."
        />
      </div>

      <ErrorAlert message={error} />

      {/* Create/Edit form */}
      {showForm && canManage && (
        <div className="mb-6 rounded-xl border border-border bg-surface-1 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              {editingId ? 'Edit codebase' : 'New codebase'}
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
                  placeholder="e.g. Concord App"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                  Default Branch
                </label>
                <input
                  type="text"
                  value={formDefaultBranch}
                  onChange={(e) => setFormDefaultBranch(e.target.value)}
                  placeholder="main"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
            </div>
            <div className="mb-3">
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                Repository URL
              </label>
              <input
                type="url"
                value={formRepoUrl}
                onChange={(e) => setFormRepoUrl(e.target.value)}
                placeholder="https://bitbucket.org/..."
                className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
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
                disabled={submitting}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                <Check size={14} />
                {submitting ? 'Saving...' : editingId ? 'Save changes' : 'Create'}
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
            New codebase
          </button>
        </div>
      )}

      {/* Grid */}
      {codebases.length === 0 ? (
        <EmptyState message="No codebases yet" />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {codebases.map((c) => (
            <CodebaseCard
              key={c.id}
              codebase={c}
              canManage={canManage}
              onEdit={startEdit}
              onDelete={promptDelete}
              onSelect={(cb) => fetchDetail(cb.id)}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="codebase"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
