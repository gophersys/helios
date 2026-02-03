import { useTheme } from '../../../theme-provider';
import { ThemeToggle } from '../../ui/theme-toggle';

export function SystemSection() {
  const { theme, toggle } = useTheme();

  return (
    <div>
      <p className="mb-6 text-sm text-text-secondary">
        General system preferences.
      </p>

      <div className="flex items-center justify-between border-t border-border-subtle py-4">
        <div>
          <div className="text-sm font-medium text-text-primary">Theme</div>
          <div className="mt-0.5 text-2xs text-text-tertiary">
            Switch between light and dark mode
          </div>
        </div>
        <ThemeToggle theme={theme} onToggle={toggle} />
      </div>
    </div>
  );
}
