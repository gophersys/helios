import { forwardRef, type SelectHTMLAttributes } from 'react';
import { ChevronDown } from 'lucide-react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Compact variant for inline/table use */
  compact?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ children, className, compact, ...props }, ref) => {
    return (
      <div
        className={[
          'relative',
          compact ? 'inline-block' : 'w-full',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
      >
        <select
          ref={ref}
          className={[
            'w-full appearance-none border border-border text-text-primary transition-colors',
            'focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent/30',
            'disabled:cursor-not-allowed disabled:opacity-50',
            compact
              ? 'rounded-md bg-surface-1 py-1.5 pl-2.5 pr-7 text-xs'
              : 'rounded-lg bg-surface-0 py-2 pl-3 pr-8 text-sm',
          ].join(' ')}
          {...props}
        >
          {children}
        </select>
        <ChevronDown
          size={compact ? 12 : 14}
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-tertiary"
        />
      </div>
    );
  }
);

Select.displayName = 'Select';
