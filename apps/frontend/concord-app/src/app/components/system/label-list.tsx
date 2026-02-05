interface LabelListProps {
  labels: Record<string, string>;
  truncateAt?: number;
}

export function LabelList({ labels, truncateAt = 40 }: LabelListProps) {
  const entries = Object.entries(labels);
  if (entries.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, v]) => (
        <span
          key={k}
          className="rounded bg-surface-2 px-2 py-0.5 font-mono text-2xs text-text-secondary"
          title={`${k}=${v}`}
        >
          {k.length > truncateAt ? `...${k.slice(-(truncateAt - 3))}` : k}={v}
        </span>
      ))}
    </div>
  );
}
