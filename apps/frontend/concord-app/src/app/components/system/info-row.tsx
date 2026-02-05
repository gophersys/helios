import { type ReactNode } from 'react';

interface InfoItem {
  label: string;
  value: ReactNode;
  mono?: boolean;
}

interface InfoRowProps {
  items: InfoItem[];
}

export function InfoRow({ items }: InfoRowProps) {
  return (
    <div className="mb-6 flex flex-wrap gap-4 text-xs text-text-tertiary">
      {items.map((item, idx) => (
        <span key={item.label}>
          {idx > 0 && <span className="mr-4 text-border">|</span>}
          {item.label}:{' '}
          <span className={item.mono ? 'font-mono text-text-secondary' : 'text-text-secondary'}>
            {item.value}
          </span>
        </span>
      ))}
    </div>
  );
}
