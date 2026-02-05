interface UsageBarProps {
  label: string;
  used: number;
  total: number;
  unit?: string;
  formatFn?: (val: number) => string;
}

function defaultFormat(val: number): string {
  return val.toLocaleString();
}

function getBarColor(pct: number): string {
  if (pct >= 90) return 'bg-error';
  if (pct >= 70) return 'bg-warning';
  return 'bg-success';
}

export function UsageBar({ label, used, total, unit = '', formatFn = defaultFormat }: UsageBarProps) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0;

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-xs font-medium text-text-secondary">{label}</span>
        <span className="text-xs tabular-nums text-text-tertiary">
          {formatFn(used)}{unit} / {formatFn(total)}{unit}
          <span className="ml-1.5 font-medium text-text-secondary">({pct.toFixed(0)}%)</span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${getBarColor(pct)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
