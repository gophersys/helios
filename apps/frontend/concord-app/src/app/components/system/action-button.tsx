import { useState } from 'react';
import { type LucideIcon } from 'lucide-react';

interface ActionButtonProps {
  label: string;
  icon: LucideIcon;
  variant: 'danger' | 'warning' | 'primary';
  confirmMessage: string;
  onConfirm: () => Promise<void>;
  onError?: (err: Error) => void;
  disabled?: boolean;
}

const variantStyles = {
  danger: 'bg-error text-white hover:bg-error-hover',
  warning: 'bg-warning text-white hover:bg-warning-hover',
  primary: 'bg-accent text-white hover:bg-accent-hover',
};

export function ActionButton({
  label,
  icon: Icon,
  variant,
  confirmMessage,
  onConfirm,
  onError,
  disabled = false,
}: ActionButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleClick = () => {
    if (!confirming) {
      setConfirming(true);
      setActionError(null);
      return;
    }
    setLoading(true);
    setActionError(null);
    onConfirm()
      .then(() => setConfirming(false))
      .catch((err) => {
        const message = err instanceof Error ? err.message : 'Action failed';
        setActionError(message);
        setConfirming(false);
        onError?.(err instanceof Error ? err : new Error(message));
      })
      .finally(() => setLoading(false));
  };

  const handleCancel = () => {
    setConfirming(false);
  };

  if (confirming) {
    return (
      <div className="flex items-center gap-2">
        {actionError && <span className="text-xs text-error">{actionError}</span>}
        <span className="text-xs text-text-secondary">{confirmMessage}</span>
        <button
          onClick={handleClick}
          disabled={loading}
          className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${variantStyles[variant]} ${
            loading ? 'opacity-50' : ''
          }`}
        >
          {loading ? 'Working...' : 'Confirm'}
        </button>
        <button
          onClick={handleCancel}
          disabled={loading}
          className="rounded px-3 py-1.5 text-xs font-medium text-text-tertiary transition-colors hover:text-text-primary"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled}
      className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
        variantStyles[variant]
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <Icon size={12} />
      {label}
    </button>
  );
}
