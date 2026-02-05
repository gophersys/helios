import { type LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  subtitle?: string;
  status?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
}

export function MetricCard({ label, value, icon: Icon, subtitle, status = 'neutral' }: MetricCardProps) {
  const statusColors: Record<string, string> = {
    success: 'text-success',
    warning: 'text-warning',
    error: 'text-error',
    info: 'text-info',
    neutral: 'text-text-primary',
  };

  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
          {label}
        </span>
        {Icon && <Icon size={14} className="text-text-tertiary" />}
      </div>
      <div className={`mt-1 text-2xl font-semibold ${statusColors[status]}`}>
        {value}
      </div>
      {subtitle && (
        <div className="mt-0.5 text-xs text-text-tertiary">{subtitle}</div>
      )}
    </div>
  );
}
