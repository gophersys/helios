import { getContext, setContext } from 'svelte';
import { browser } from '$app/environment';

type Theme = 'light' | 'dark';

class ThemeState {
  theme = $state<Theme>('dark');

  constructor() {
    if (browser) {
      const stored = localStorage.getItem('concord-theme') as Theme | null;
      if (stored) {
        this.theme = stored;
      } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        this.theme = 'dark';
      } else {
        this.theme = 'light';
      }
      this.applyTheme();
    }
  }

  private applyTheme(): void {
    if (!browser) return;
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(this.theme);
  }

  toggle(): void {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    if (browser) {
      localStorage.setItem('concord-theme', this.theme);
      this.applyTheme();
    }
  }
}

const THEME_KEY = Symbol('theme');

export function createThemeContext(): ThemeState {
  const theme = new ThemeState();
  setContext(THEME_KEY, theme);
  return theme;
}

export function getTheme(): ThemeState {
  return getContext<ThemeState>(THEME_KEY);
}
