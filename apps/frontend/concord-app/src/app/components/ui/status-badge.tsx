const COLORS: Record<string, string> = {
  ACTIVE: 'bg-success-muted text-success',
  DEPRECATED: 'bg-warning-muted text-warning',
  EOL: 'bg-error-muted text-error',
  DRAFT: 'bg-accent-muted text-accent',
  RELEASED: 'bg-success-muted text-success',
  UPLOAD: 'bg-accent-muted text-accent',
  EXTERNAL: 'bg-surface-2 text-text-secondary',
};

export function StatusBadge({ status }: { status: string }) {
  const colorClass = COLORS[status] || 'bg-surface-2 text-text-secondary';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-2xs font-medium ${colorClass}`}
    >
      {status}
    </span>
  );
}
