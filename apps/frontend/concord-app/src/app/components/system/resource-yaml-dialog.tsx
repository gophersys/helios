import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Pencil, Eye } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { useAuth } from '../../auth-provider';
import { LoadingState } from '../ui/loading-state';
import { YamlViewer } from './yaml-viewer';
import { YamlEditor } from './yaml-editor';
import { ResourceYamlData } from '../../types/models';

interface ResourceYamlDialogProps {
  kind: string;
  namespace: string;
  name: string;
  open: boolean;
  onClose: () => void;
}

export function ResourceYamlDialog({ kind, namespace, name, open, onClose }: ResourceYamlDialogProps) {
  const { hasPermission } = useAuth();
  const [data, setData] = useState<ResourceYamlData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const canManage = hasPermission('Concord.Admin.System.Manage');

  const fetchYaml = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<ApiResponse<ResourceYamlData>>(
        `/v2/system/resources/${kind}/${namespace}/${name}`
      );
      setData(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load YAML');
    } finally {
      setLoading(false);
    }
  }, [kind, namespace, name]);

  useEffect(() => {
    if (open) {
      fetchYaml();
      setEditing(false);
    }
  }, [open, fetchYaml]);

  // Escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [open, onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = ''; };
    }
  }, [open]);

  const handleApply = async (yaml: string) => {
    await api(`/v2/system/resources/${kind}/${namespace}/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml }),
    });
    await fetchYaml();
    setEditing(false);
  };

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-xl border border-border bg-surface-1 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-text-primary">
              {data?.kind || kind} — {namespace}/{name}
            </h3>
            {data?.apiVersion && (
              <span className="rounded bg-surface-2 px-2 py-0.5 text-2xs text-text-tertiary">
                {data.apiVersion}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {canManage && data && (
              <button
                onClick={() => setEditing(!editing)}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-tertiary transition-colors hover:text-text-primary"
              >
                {editing ? <Eye size={12} /> : <Pencil size={12} />}
                {editing ? 'View' : 'Edit'}
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded p-1 text-text-tertiary transition-colors hover:text-text-primary"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="max-h-[75vh] overflow-auto p-4">
          {loading ? (
            <LoadingState message="Loading YAML..." />
          ) : error ? (
            <div className="text-center text-sm text-error">{error}</div>
          ) : data ? (
            editing ? (
              <YamlEditor
                initialYaml={data.yaml}
                onApply={handleApply}
                onCancel={() => setEditing(false)}
              />
            ) : (
              <YamlViewer yaml={data.yaml} />
            )
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}
