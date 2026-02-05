import { useState } from 'react';
import { Download, Trash2 } from 'lucide-react';
import { api } from '../../api';
import { StatusBadge } from '../../components/ui/status-badge';
import { ErrorAlert } from '../../components/ui/error-alert';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { ApiResponse } from '../../types';
import { FirmwareBuildUpload } from './firmware-build-upload';
import { FirmwareBuild, BoardRevision } from '../../types/models';

function formatBytes(bytes: string | null): string {
  if (!bytes) return '—';
  const n = parseInt(bytes, 10);
  if (isNaN(n)) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function FirmwareBuildList({
  productId,
  applicationId,
  builds,
  boardRevisions,
  canManage,
  onRefresh,
}: {
  productId: string;
  applicationId: string;
  builds: FirmwareBuild[];
  boardRevisions: BoardRevision[];
  canManage: boolean;
  onRefresh: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const handleDownload = async (buildId: string) => {
    try {
      const res = await api<ApiResponse<{ url: string; filename: string }>>(
        `/v2/products/firmware-builds/${buildId}/download`
      );
      window.open(res.data.url, '_blank');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to download');
    }
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await api(`/v2/products/${productId}/firmware-builds/${id}`, { method: 'DELETE' });
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-2xs font-medium text-text-secondary">Builds</span>
        {canManage && !showUpload && (
          <button
            onClick={() => setShowUpload(true)}
            className="flex items-center gap-1 rounded bg-accent/10 px-2 py-1 text-2xs font-medium text-accent hover:bg-accent/20"
          >
            Upload build
          </button>
        )}
      </div>

      <ErrorAlert message={error} />

      {showUpload && (
        <FirmwareBuildUpload
          productId={productId}
          applicationId={applicationId}
          boardRevisions={boardRevisions}
          onClose={() => setShowUpload(false)}
          onSuccess={() => {
            setShowUpload(false);
            onRefresh();
          }}
        />
      )}

      {builds.length > 0 ? (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Version</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Board Rev</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Status</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Size</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Mfg</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Date</th>
                <th className="px-3 py-2 text-right text-2xs font-medium text-text-tertiary">Actions</th>
              </tr>
            </thead>
            <tbody>
              {builds.map((b) => (
                <tr key={b.id} className="border-b border-border-subtle last:border-0 hover:bg-surface-1">
                  <td className="px-3 py-2 font-medium text-text-primary">
                    <div>{b.version}</div>
                    <div className="text-2xs text-text-tertiary">{b.filename}</div>
                  </td>
                  <td className="px-3 py-2 text-text-secondary">{b.boardRevisionVersion || '—'}</td>
                  <td className="px-3 py-2"><StatusBadge status={b.status} /></td>
                  <td className="px-3 py-2 text-text-secondary">{formatBytes(b.sizeBytes)}</td>
                  <td className="px-3 py-2">
                    {b.isManufacturing ? (
                      <span className="rounded bg-warning-muted px-1.5 py-0.5 text-2xs font-medium text-warning">Mfg</span>
                    ) : (
                      <span className="text-text-tertiary">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-2xs text-text-tertiary">
                    {new Date(b.createdAt).toLocaleDateString()}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => handleDownload(b.id)}
                        className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-accent"
                        title="Download"
                        aria-label="Download"
                      >
                        <Download size={13} />
                      </button>
                      {canManage && (
                        <button
                          onClick={() => setDeleteTarget({ id: b.id, name: b.version })}
                          className="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                          title="Delete"
                          aria-label="Delete"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="py-4 text-center text-2xs text-text-tertiary">
          No builds yet
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="firmware build"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
