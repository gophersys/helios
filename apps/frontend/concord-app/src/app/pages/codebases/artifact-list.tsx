import { useState } from 'react';
import { Download, Trash2, Plus, Check, X, Link } from 'lucide-react';
import { api, apiUploadRaw } from '../../api';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { ErrorAlert } from '../../components/ui/error-alert';
import { StatusBadge } from '../../components/ui/status-badge';
import { ApiResponse } from '../../types';
import { formatSize } from '../../utils/formatting';
import { ArtifactUpload } from './artifact-upload';
import { Artifact } from '../../types/models';

export function ArtifactList({
  codebaseId,
  releaseId,
  artifacts,
  canManage,
  onRefresh,
}: {
  codebaseId: string;
  releaseId: string;
  artifacts: Artifact[];
  canManage: boolean;
  onRefresh: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{id: string, name: string} | null>(null);
  const [showExternalForm, setShowExternalForm] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [extName, setExtName] = useState('');
  const [extUrl, setExtUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const promptDelete = (artifactId: string) => {
    const art = artifacts.find((a: Artifact) => a.id === artifactId);
    setDeleteTarget({ id: artifactId, name: art?.name || '' });
  };

  const handleDelete = async (artifactId: string) => {
    setError(null);
    try {
      await api(
        `/v2/codebases/${codebaseId}/releases/${releaseId}/artifacts/${artifactId}`,
        { method: 'DELETE' }
      );
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete artifact');
    }
  };

  const handleDownload = async (artifactId: string) => {
    try {
      const res = await api<ApiResponse<{ url: string }>>(
        `/v2/codebases/artifacts/${artifactId}/download`
      );
      window.open(res.data.url, '_blank');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to get download URL');
    }
  };

  const handleCreateExternal = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api(`/v2/codebases/${codebaseId}/releases/${releaseId}/artifacts`, {
        method: 'POST',
        body: JSON.stringify({ name: extName, externalUrl: extUrl }),
      });
      setExtName('');
      setExtUrl('');
      setShowExternalForm(false);
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create artifact');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUploadFile = async (file: File) => {
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);

      await apiUploadRaw(
        `/v2/codebases/${codebaseId}/releases/${releaseId}/artifacts/upload`,
        formData
      );

      setShowUpload(false);
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to upload artifact');
    }
  };

  return (
    <div className="mt-2">
      <ErrorAlert message={error} />

      {artifacts.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-3 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Name
                </th>
                <th className="px-3 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Type
                </th>
                <th className="px-3 py-2 text-left text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Size
                </th>
                <th className="px-3 py-2 text-right text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {artifacts.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-border-subtle last:border-0 hover:bg-surface-1"
                >
                  <td className="px-3 py-2">
                    <div className="font-medium text-text-primary">{a.name}</div>
                    {a.filename && a.filename !== a.name && (
                      <div className="text-2xs text-text-tertiary">{a.filename}</div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={a.type} />
                  </td>
                  <td className="px-3 py-2 text-text-secondary text-2xs">
                    {formatSize(a.sizeBytes)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleDownload(a.id)}
                        className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-accent"
                        title="Download"
                        aria-label="Download"
                      >
                        <Download size={14} />
                      </button>
                      {canManage && (
                        <button
                          onClick={() => promptDelete(a.id)}
                          className="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                          title="Delete"
                          aria-label="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {artifacts.length === 0 && (
        <div className="py-3 text-center text-2xs text-text-tertiary">No artifacts</div>
      )}

      {/* Add buttons */}
      {canManage && (
        <div className="mt-2 flex gap-2">
          {!showUpload && !showExternalForm && (
            <>
              <button
                onClick={() => setShowUpload(true)}
                className="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
              >
                <Plus size={12} />
                Upload file
              </button>
              <button
                onClick={() => setShowExternalForm(true)}
                className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2"
              >
                <Link size={12} />
                Add external link
              </button>
            </>
          )}
        </div>
      )}

      {/* Upload zone */}
      {showUpload && (
        <div className="mt-2">
          <ArtifactUpload onUpload={handleUploadFile} />
          <button
            onClick={() => setShowUpload(false)}
            className="mt-1 text-2xs text-text-tertiary hover:text-text-secondary"
          >
            Cancel
          </button>
        </div>
      )}

      {/* External link form */}
      {showExternalForm && (
        <form
          onSubmit={handleCreateExternal}
          className="mt-2 rounded-lg border border-border bg-surface-0 p-3"
        >
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                Name
              </label>
              <input
                type="text"
                required
                value={extName}
                onChange={(e) => setExtName(e.target.value)}
                placeholder="e.g. Release Notes PDF"
                className="w-full rounded-lg border border-border bg-surface-1 px-3 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                URL
              </label>
              <input
                type="url"
                required
                value={extUrl}
                onChange={(e) => setExtUrl(e.target.value)}
                placeholder="https://..."
                className="w-full rounded-lg border border-border bg-surface-1 px-3 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
          </div>
          <div className="mt-2 flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              <Check size={12} />
              {submitting ? 'Adding...' : 'Add'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowExternalForm(false);
                setExtName('');
                setExtUrl('');
              }}
              className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2"
            >
              <X size={12} />
              Cancel
            </button>
          </div>
        </form>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="artifact"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
