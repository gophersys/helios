import { useState } from 'react';
import { Plus, X, Check, Pencil, Trash2 } from 'lucide-react';
import { Select } from '../../components/ui/select';
import { api } from '../../api';
import { StatusBadge } from '../../components/ui/status-badge';
import { ErrorAlert } from '../../components/ui/error-alert';
import { ConfirmDeleteDialog } from '../../components/ui/confirm-delete-dialog';
import { ApiResponse } from '../../types';
import { BoardRevision } from '../../types/models';

function ChipsetTagInput({
  value,
  onChange,
  supportedSocs,
}: {
  value: string[];
  onChange: (chipsets: string[]) => void;
  supportedSocs: string[];
}) {
  const available = supportedSocs.filter((s) => !value.includes(s));

  const removeChipset = (chip: string) => {
    onChange(value.filter((c) => c !== chip));
  };

  return (
    <div className="flex min-h-[38px] flex-wrap items-center gap-1.5 rounded-lg border border-border bg-surface-0 px-2.5 py-1.5 focus-within:border-accent">
      {value.map((chip) => (
        <span
          key={chip}
          className="inline-flex items-center gap-1 rounded bg-accent/10 px-1.5 py-0.5 text-2xs font-medium text-accent"
        >
          {chip}
          <button
            type="button"
            onClick={() => removeChipset(chip)}
            aria-label="Remove chipset"
            className="ml-0.5 rounded-full p-0.5 hover:bg-accent/20"
          >
            <X size={10} />
          </button>
        </span>
      ))}
      {available.length > 0 && (
        <Select
          compact
          value=""
          onChange={(e) => {
            if (e.target.value) onChange([...value, e.target.value]);
          }}
          className="min-w-[100px] flex-1"
        >
          <option value="">{value.length === 0 ? 'Select SoCs...' : 'Add another...'}</option>
          {available.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      )}
    </div>
  );
}

export function BoardRevisionList({
  productId,
  revisions,
  supportedSocs,
  canManage,
  onRefresh,
}: {
  productId: string;
  revisions: BoardRevision[];
  supportedSocs: string[];
  canManage: boolean;
  onRefresh: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formVersion, setFormVersion] = useState('');
  const [formChipsets, setFormChipsets] = useState<string[]>([]);
  const [formStatus, setFormStatus] = useState('ACTIVE');
  const [formNotes, setFormNotes] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const resetForm = () => {
    setFormVersion('');
    setFormChipsets([]);
    setFormStatus('ACTIVE');
    setFormNotes('');
    setEditingId(null);
    setShowForm(false);
  };

  const startEdit = (r: BoardRevision) => {
    setFormVersion(r.version);
    setFormChipsets(r.chipsets || []);
    setFormStatus(r.status);
    setFormNotes(r.notes || '');
    setEditingId(r.id);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body = {
      version: formVersion,
      chipsets: formChipsets,
      status: formStatus,
      notes: formNotes || null,
    };

    try {
      if (editingId) {
        await api(`/v2/products/${productId}/board-revisions/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        });
      } else {
        await api(`/v2/products/${productId}/board-revisions`, {
          method: 'POST',
          body: JSON.stringify(body),
        });
      }
      resetForm();
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save board revision');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await api(`/v2/products/${productId}/board-revisions/${id}`, { method: 'DELETE' });
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">Board Revisions</h3>
        {canManage && !showForm && (
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
          >
            <Plus size={13} />
            Add revision
          </button>
        )}
      </div>

      <ErrorAlert message={error} />

      {showForm && (
        <div className="mb-4 rounded-lg border border-border bg-surface-0 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-2xs font-medium text-text-secondary">
              {editingId ? 'Edit revision' : 'New revision'}
            </span>
            <button onClick={resetForm} className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary">
              <X size={14} />
            </button>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="mb-3 grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Version</label>
                <input
                  type="text"
                  required
                  value={formVersion}
                  onChange={(e) => setFormVersion(e.target.value)}
                  placeholder="e.g. A0, B1"
                  className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-2xs font-medium text-text-tertiary">Status</label>
                <Select
                  value={formStatus}
                  onChange={(e) => setFormStatus(e.target.value)}
                >
                  <option value="ACTIVE">Active</option>
                  <option value="DEPRECATED">Deprecated</option>
                  <option value="EOL">EOL</option>
                </Select>
              </div>
            </div>
            <div className="mb-3">
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">
                Chipsets
                <span className="ml-1 font-normal text-text-tertiary/70">— press Enter or comma to add</span>
              </label>
              <ChipsetTagInput value={formChipsets} onChange={setFormChipsets} supportedSocs={supportedSocs} />
            </div>
            <div className="mb-3">
              <label className="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
              <input
                type="text"
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="Optional notes"
                className="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={submitting} className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
                <Check size={12} />
                {submitting ? 'Saving...' : editingId ? 'Save' : 'Create'}
              </button>
              <button type="button" onClick={resetForm} className="rounded-lg px-3 py-1.5 text-2xs font-medium text-text-secondary hover:bg-surface-2">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {revisions.length > 0 ? (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2">
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Version</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Chipsets</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Status</th>
                <th className="px-3 py-2 text-left text-2xs font-medium text-text-tertiary">Notes</th>
                {canManage && <th className="px-3 py-2 text-right text-2xs font-medium text-text-tertiary">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {revisions.map((r) => (
                <tr key={r.id} className="border-b border-border-subtle last:border-0 hover:bg-surface-1">
                  <td className="px-3 py-2 font-medium text-text-primary">{r.version}</td>
                  <td className="px-3 py-2">
                    {r.chipsets.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {r.chipsets.map((c) => (
                          <span key={c} className="rounded bg-accent/10 px-1.5 py-0.5 text-2xs font-medium text-accent">
                            {c}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-text-tertiary">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                  <td className="px-3 py-2 text-text-tertiary">{r.notes || '—'}</td>
                  {canManage && (
                    <td className="px-3 py-2 text-right">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => startEdit(r)}
                          className="rounded p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
                          title="Edit"
                          aria-label="Edit"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          onClick={() => setDeleteTarget({ id: r.id, name: r.version })}
                          className="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                          title="Delete"
                          aria-label="Delete"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="py-6 text-center text-sm text-text-tertiary">
          No board revisions yet
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!deleteTarget}
        entityType="board revision"
        entityName={deleteTarget?.name || ''}
        onConfirm={() => { handleDelete(deleteTarget!.id); setDeleteTarget(null); }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
