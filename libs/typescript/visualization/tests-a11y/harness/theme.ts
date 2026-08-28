/**
 * The a11y-evidence harness theme injection (mirrors @eden/primitives' harness, RD-16).
 *
 * @eden/theme is pure data + a generator (ADR-0024). We generate the light-mode theme from the C21
 * brand seed and emit the `:root { --color-*: oklch(...); --space-*: Npx; ... }` block, then inject it
 * as the FIRST child of <head> so the tokens are defined before any component styles and cascade to
 * the document. The HotspotMap derives its OWN `--eden-hotspot-map-*` vars from the same theme; this
 * block is the surrounding token context the axe color-contrast rule and the resolved-token assertions
 * read (so axe evaluates the chart text against the real Eden reading background, not the UA white).
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
  document.body.style.background = 'var(--color-surface)';
  document.body.style.color = 'var(--color-on-surface)';
  window.__EDEN_THEME__ = theme;
  window.__EDEN_CSS__ = cssText;
}
