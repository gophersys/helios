/**
 * Tests for the theme store.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { setupLocalStorageMock, type MockStorage } from '../../tests/helpers';

// Mock modules
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('svelte', () => ({
  getContext: vi.fn(),
  setContext: vi.fn()
}));

import { createThemeContext, getTheme } from './theme.svelte';
import { getContext, setContext } from 'svelte';

describe('ThemeState', () => {
  let storage: MockStorage;
  let mockMatchMedia: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    storage = setupLocalStorageMock();
    vi.clearAllMocks();

    // Mock matchMedia
    mockMatchMedia = vi.fn().mockReturnValue({
      matches: false,
      media: '',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn()
    });
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: mockMatchMedia
    });

    // Mock document.documentElement.classList
    document.documentElement.classList.remove('light', 'dark');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('createThemeContext', () => {
    it('creates ThemeState and sets context', () => {
      const theme = createThemeContext();

      expect(setContext).toHaveBeenCalled();
      expect(theme).toBeDefined();
    });
  });

  describe('getTheme', () => {
    it('retrieves theme from context', () => {
      const mockTheme = { theme: 'dark' };
      vi.mocked(getContext).mockReturnValue(mockTheme);

      const result = getTheme();

      expect(getContext).toHaveBeenCalled();
      expect(result).toBe(mockTheme);
    });
  });

  describe('Initial theme', () => {
    it('uses stored theme from localStorage', () => {
      storage._store['concord-theme'] = 'light';

      const theme = createThemeContext();

      expect(theme.theme).toBe('light');
    });

    it('uses dark theme when prefers-color-scheme is dark', () => {
      mockMatchMedia.mockReturnValue({ matches: true });

      const theme = createThemeContext();

      expect(theme.theme).toBe('dark');
    });

    it('uses light theme when prefers-color-scheme is light', () => {
      mockMatchMedia.mockReturnValue({ matches: false });

      const theme = createThemeContext();

      // Default is dark in the code, but if light scheme is preferred
      // Actually, looking at the code, if no stored theme and prefers-color-scheme
      // is not dark, it sets to 'light'
      expect(theme.theme).toBe('light');
    });

    it('applies theme class to document on creation', () => {
      storage._store['concord-theme'] = 'dark';

      createThemeContext();

      expect(document.documentElement.classList.contains('dark')).toBe(true);
    });
  });

  describe('toggle', () => {
    it('switches from dark to light', () => {
      storage._store['concord-theme'] = 'dark';
      const theme = createThemeContext();

      theme.toggle();

      expect(theme.theme).toBe('light');
    });

    it('switches from light to dark', () => {
      storage._store['concord-theme'] = 'light';
      const theme = createThemeContext();

      theme.toggle();

      expect(theme.theme).toBe('dark');
    });

    it('persists new theme to localStorage', () => {
      storage._store['concord-theme'] = 'dark';
      const theme = createThemeContext();

      theme.toggle();

      expect(storage._store['concord-theme']).toBe('light');
    });

    it('updates document class on toggle', () => {
      storage._store['concord-theme'] = 'dark';
      const theme = createThemeContext();

      theme.toggle();

      expect(document.documentElement.classList.contains('light')).toBe(true);
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    it('removes old theme class when toggling', () => {
      storage._store['concord-theme'] = 'light';
      const theme = createThemeContext();
      expect(document.documentElement.classList.contains('light')).toBe(true);

      theme.toggle();

      expect(document.documentElement.classList.contains('light')).toBe(false);
      expect(document.documentElement.classList.contains('dark')).toBe(true);
    });
  });
});
