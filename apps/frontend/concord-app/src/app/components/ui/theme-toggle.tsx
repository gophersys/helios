import { Sun, Moon } from 'lucide-react';

export function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: string;
  onToggle: () => void;
}) {
  const isDark = theme === 'dark';

  return (
    <button
      onClick={onToggle}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={[
        'relative flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-300',
        isDark ? 'bg-surface-2' : 'bg-warning',
      ].join(' ')}
    >
      <div
        className={[
          'absolute flex h-4 w-4 items-center justify-center rounded-full bg-white shadow-sm transition-all duration-300 ease-in-out',
          isDark ? 'left-[26px]' : 'left-[3px]',
        ].join(' ')}
      >
        {isDark ? (
          <Moon size={10} strokeWidth={2.5} className="text-text-primary" />
        ) : (
          <Sun size={10} strokeWidth={2.5} className="text-warning" />
        )}
      </div>
    </button>
  );
}
