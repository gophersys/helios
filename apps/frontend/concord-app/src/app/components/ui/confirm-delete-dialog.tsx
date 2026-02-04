import { useState, useEffect, useRef } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDeleteDialogProps {
  open: boolean;
  entityType: string;
  entityName: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDeleteDialog({
  open,
  entityType,
  entityName,
  onConfirm,
  onCancel,
}: ConfirmDeleteDialogProps) {
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const matches = inputValue === entityName;

  useEffect(() => {
    if (open) {
      setInputValue('');
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (matches) onConfirm();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onCancel}
      />

      {/* Dialog */}
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-md rounded-xl border border-border bg-surface-1 p-6 shadow-xl animate-fade-in"
      >
        <button
          type="button"
          onClick={onCancel}
          className="absolute right-4 top-4 rounded-lg p-1 text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
        >
          <X size={16} />
        </button>

        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-error-muted">
            <AlertTriangle size={20} className="text-error" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">
              Delete {entityType}
            </h3>
            <p className="text-2xs text-text-tertiary">
              This action cannot be undone.
            </p>
          </div>
        </div>

        <p className="mb-4 text-sm text-text-secondary">
          To confirm, type{' '}
          <span className="font-semibold text-text-primary">{entityName}</span>{' '}
          below:
        </p>

        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={entityName}
          className="mb-4 w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          autoComplete="off"
          spellCheck={false}
        />

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-2"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!matches}
            className="rounded-lg bg-error px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Delete
          </button>
        </div>
      </form>
    </div>
  );
}
