import { ArrowLeft } from 'lucide-react';

export function BackButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="mb-4 flex items-center gap-1.5 rounded-lg px-2 py-1.5 -ml-2 text-xs font-medium text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
    >
      <ArrowLeft size={14} strokeWidth={2} />
      {label}
    </button>
  );
}
