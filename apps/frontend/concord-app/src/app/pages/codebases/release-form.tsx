import { useState } from 'react';
import { Check, X } from 'lucide-react';

interface ReleaseFormProps {
  onSubmit: (data: {
    version: string;
    status: string;
    releaseNotes: string | null;
    tagName: string | null;
  }) => Promise<void>;
  onCancel: () => void;
  initial?: {
    version: string;
    status: string;
    releaseNotes: string | null;
    tagName: string | null;
  };
}

export function ReleaseForm({ onSubmit, onCancel, initial }: ReleaseFormProps) {
  const [version, setVersion] = useState(initial?.version || '');
  const [status, setStatus] = useState(initial?.status || 'DRAFT');
  const [releaseNotes, setReleaseNotes] = useState(initial?.releaseNotes || '');
  const [tagName, setTagName] = useState(initial?.tagName || '');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        version,
        status,
        releaseNotes: releaseNotes || null,
        tagName: tagName || null,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-border bg-surface-0 p-3"
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <label className="mb-1 block text-2xs font-medium text-text-tertiary">
            Version
          </label>
          <input
            type="text"
            required
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="e.g. 1.0.0"
            className="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-2xs font-medium text-text-tertiary">
            Status
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="DRAFT">Draft</option>
            <option value="RELEASED">Released</option>
            <option value="DEPRECATED">Deprecated</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-2xs font-medium text-text-tertiary">
            Tag Name
          </label>
          <input
            type="text"
            value={tagName}
            onChange={(e) => setTagName(e.target.value)}
            placeholder="e.g. v1.0.0"
            className="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-2xs font-medium text-text-tertiary">
            Release Notes
          </label>
          <input
            type="text"
            value={releaseNotes}
            onChange={(e) => setReleaseNotes(e.target.value)}
            placeholder="Optional"
            className="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          <Check size={13} />
          {initial ? 'Save' : 'Create'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
