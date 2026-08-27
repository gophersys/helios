/**
 * The a11y-evidence harness theme injection (mirrors the OD-1 spike, RD-16).
 *
 * @eden/theme is pure data + a generator (ADR-0024). We generate the light-mode theme from the C21
 * brand seed and emit the `:root { --color-*: oklch(...); --space-*: Npx; ... }` block, then inject
 * it as the FIRST child of <head> so the tokens are defined before any component styles and cascade
 * to the bits-ui Portal host (document.body) and beyond. The Button derives its OWN `--eden-button-*`
 * vars from the same theme via deriveButtonTokens — this block is the surrounding token context the
 * axe color-contrast rule and the resolved-token assertions read.
 */
import { generateTheme, themeToCssVariables, C21_SEED, type Theme } from '@eden/theme';

declare global {
  interface Window {
    __EDEN_THEME__: Theme;
    __EDEN_CSS__: string;
  }
}

export const theme: Theme = generateTheme(C21_SEED, { mode: 'light' });
export const cssText: string = themeToCssVariables(theme);

export function injectEdenTokens(): void {
  const style = document.createElement('style');
  style.id = 'eden-tokens';
  style.textContent = cssText;
  document.head.insertBefore(style, document.head.firstChild);
  // The harness page must also paint the surface so axe's color-contrast rule evaluates the button
  // against the real Eden reading background (not the UA default white).
  document.body.style.background = 'var(--color-surface)';
  document.body.style.color = 'var(--color-on-surface)';
  window.__EDEN_THEME__ = theme;
  window.__EDEN_CSS__ = cssText;
}
