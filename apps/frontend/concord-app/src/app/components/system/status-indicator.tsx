const STATUS_MAP: Record<string, { color: string; bg: string }> = {
  Ready: { color: 'bg-success', bg: 'bg-success-muted' },
  Running: { color: 'bg-success', bg: 'bg-success-muted' },
  Active: { color: 'bg-success', bg: 'bg-success-muted' },
  Succeeded: { color: 'bg-success', bg: 'bg-success-muted' },
  Pending: { color: 'bg-warning', bg: 'bg-warning-muted' },
  NotReady: { color: 'bg-error', bg: 'bg-error-muted' },
  Failed: { color: 'bg-error', bg: 'bg-error-muted' },
  Error: { color: 'bg-error', bg: 'bg-error-muted' },
  Unknown: { color: 'bg-text-tertiary', bg: 'bg-surface-2' },
  Warning: { color: 'bg-warning', bg: 'bg-warning-muted' },
  Normal: { color: 'bg-success', bg: 'bg-success-muted' },
};

export function StatusIndicator({ status }: { status: string }) {
  const style = STATUS_MAP[status] || STATUS_MAP.Unknown;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${style.bg}`}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${style.color}`} />
      {status}
    </span>
  );
}
