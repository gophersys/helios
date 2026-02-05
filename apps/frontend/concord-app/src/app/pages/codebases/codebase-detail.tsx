import { useState } from 'react';
import { Plus, ExternalLink, ChevronDown, ChevronRight, Pencil, Trash2 } from 'lucide-react';
import { api } from '../../api';
import { BackButton } from '../../components/ui/back-button';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { ErrorAlert } from '../../components/ui/error-alert';
import { StatusBadge } from '../../components/ui/status-badge';
import { ImageUpload } from '../inventory/image-upload';
import { ReleaseForm } from './release-form';
import { ApiResponse } from '../../types';
import { ArtifactList } from './artifact-list';
import { Codebase, Release } from '../../types/models';
import { isSafeUrl } from '../../utils/url';

export function CodebaseDetail({
  codebase,
  canManage,
  onBack,
  onRefresh,
  onImageUpload,
}: {
  codebase: Codebase;
  canManage: boolean;
  onBack: () => void;
  onRefresh: () => void;
  onImageUpload: (file: File) => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{id: string, name: string} | null>(null);
  const [showReleaseForm, setShowReleaseForm] = useState(false);
  const [editingRelease, setEditingRelease] = useState<Release | null>(null);
  const [expandedReleases, setExpandedReleases] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedReleases((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleCreateRelease = async (data: {
    version: string;
    status: string;
    releaseNotes: string | null;
    tagName: string | null;
  }) => {
    setError(null);
    try {
      await api(`/v2/codebases/${codebase.id}/releases`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
      setShowReleaseForm(false);
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create release');
    }
  };

  const handleUpdateRelease = async (
    releaseId: string,
    data: {
      version: string;
      status: string;
      releaseNotes: string | null;
      tagName: string | null;
    }
  ) => {
    setError(null);
    try {
      await api(`/v2/codebases/${codebase.id}/releases/${releaseId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
      setEditingRelease(null);
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update release');
    }
  };

  const promptDeleteRelease = (releaseId: string) => {
    const rel = releases.find((r: Release) => r.id === releaseId);
    setDeleteTarget({ id: releaseId, name: rel?.version || '' });
  };

  const handleDeleteRelease = async (releaseId: string) => {
    setError(null);
    try {
      await api(`/v2/codebases/${codebase.id}/releases/${releaseId}`, {
        method: 'DELETE',
      });
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete release');
    }
  };

  const releases = codebase.releases || [];

  return (
    <div className="animate-fade-in">
      <BackButton label="Back to codebases" onClick={onBack} />

      <ErrorAlert message={error} />

      <div className="rounded-xl border border-border bg-surface-1 p-5">
        <div className="flex gap-6">
          {/* Image */}
          <div className="w-48 shrink-0">
            <ImageUpload
              currentUrl={codebase.imageUrl}
              onUpload={onImageUpload}
              disabled={!canManage}
            />
          </div>

          {/* Info */}
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-text-primary">
              {codebase.name}
            </h2>
            {codebase.description && (
              <p className="mt-1 text-sm text-text-secondary">
                {codebase.description}
              </p>
            )}
            <div className="mt-3 flex gap-4 text-2xs text-text-tertiary">
              <span>
                <strong className="text-text-secondary">Branch:</strong>{' '}
                {codebase.defaultBranch}
              </span>
              {codebase.repoUrl && isSafeUrl(codebase.repoUrl) && (
                <a
                  href={codebase.repoUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-accent hover:underline"
                >
                  <ExternalLink size={11} />
                  Repository
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Releases */}
        <div className="mt-6">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">Releases</h3>
            {canManage && !showReleaseForm && (
              <button
                onClick={() => setShowReleaseForm(true)}
                className="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
              >
                <Plus size={13} />
                Add release
              </button>
            )}
          </div>

          {showReleaseForm && (
            <div className="mb-4">
              <ReleaseForm
                onSubmit={handleCreateRelease}
                onCancel={() => setShowReleaseForm(false)}
              />
            </div>
          )}

          {releases.length > 0 ? (
            <div className="space-y-2">
              {releases.map((release) => {
                const isExpanded = expandedReleases.has(release.id);
                const isEditing = editingRelease?.id === release.id;

                return (
                  <div
                    key={release.id}
                    className="rounded-lg border border-border bg-surface-0"
                  >
                    {/* Release header */}
                    <div
                      className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-surface-1"
                      onClick={() => toggleExpanded(release.id)}
                    >
                      {isExpanded ? (
                        <ChevronDown size={14} className="shrink-0 text-text-tertiary" />
                      ) : (
                        <ChevronRight size={14} className="shrink-0 text-text-tertiary" />
                      )}
                      <span className="font-medium text-text-primary text-sm">
                        {release.version}
                      </span>
                      <StatusBadge status={release.status} />
                      {release.tagName && (
                        <span className="text-2xs text-text-tertiary">
                          tag: {release.tagName}
                        </span>
                      )}
                      {release.releasedAt && (
                        <span className="text-2xs text-text-tertiary">
                          {new Date(release.releasedAt).toLocaleDateString()}
                        </span>
                      )}
                      <span className="ml-auto text-2xs text-text-tertiary">
                        {release.artifactCount || 0} artifact
                        {(release.artifactCount || 0) !== 1 ? 's' : ''}
                      </span>

                      {canManage && (
                        <div
                          className="flex gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={() => setEditingRelease(release)}
                            className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                            title="Edit release"
                            aria-label="Edit release"
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            onClick={() => promptDeleteRelease(release.id)}
                            className="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                            title="Delete release"
                            aria-label="Delete release"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Release notes */}
                    {isExpanded && release.releaseNotes && (
                      <div className="border-t border-border-subtle px-4 py-2 text-sm text-text-secondary">
                        {release.releaseNotes}
                      </div>
                    )}

                    {/* Editing form */}
                    {isEditing && (
                      <div className="border-t border-border px-4 py-3">
                        <ReleaseForm
                          initial={{
                            version: release.version,
                            status: release.status,
                            releaseNotes: release.releaseNotes,
                            tagName: release.tagName,
                          }}
                          onSubmit={(data) =>
                            handleUpdateRelease(release.id, data)
                          }
                          onCancel={() => setEditingRelease(null)}
                        />
                      </div>
                    )}

                    {/* Artifacts */}
                    {isExpanded && (
                      <div className="border-t border-border-subtle px-4 py-3">
                        <ArtifactList
                          codebaseId={codebase.id}
                          releaseId={release.id}
                          artifacts={release.artifacts || []}
                          canManage={canManage}
                          onRefresh={onRefresh}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-6 text-center text-sm text-text-tertiary">
              No releases yet
            </div>
          )}
        </div>
      </div>

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="release"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDeleteRelease(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
