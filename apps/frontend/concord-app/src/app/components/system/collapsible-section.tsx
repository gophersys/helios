import { useState, type ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function CollapsibleSection({ title, count, defaultOpen = false, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="mb-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2 text-left transition-colors hover:bg-surface-2/80"
      >
        <ChevronRight
          size={14}
          className={`text-text-tertiary transition-transform ${open ? 'rotate-90' : ''}`}
        />
        <span className="text-sm font-medium text-text-primary">{title}</span>
        {count !== undefined && (
          <span className="rounded bg-surface-1 px-1.5 py-0.5 text-2xs text-text-tertiary">
            {count}
          </span>
        )}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  );
}
