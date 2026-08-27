/**
 * Deep-link helpers: build/parse URLs, trigger the highlight animation.
 *
 * The highlight effect is triggered by the root layout's `afterNavigate`
 * handler. This module is the pure logic — no Svelte, no DOM effects
 * outside the exported highlight function.
 */

import { isActionableId, type ActionableId } from './registry';

/** Query-param name used for the deep-link action ID. */
export const DEEP_LINK_PARAM = 'a';

/** How long the highlight pulse stays on the target element. */
const HIGHLIGHT_DURATION_MS = 2400;

/**
 * Build a deep-link URL for the given action from the current page.
 *
 * Preserves the path + existing query params (tab, revision, etc.) and
 * adds/replaces the `?a=` param. This means the copied link lands on
 * exactly the UI state the user was looking at, with the action
 * highlighted.
 */
export function buildDeepLink(actionId: ActionableId, currentUrl: URL): string {
  const next = new URL(currentUrl.toString());
  next.searchParams.set(DEEP_LINK_PARAM, actionId);
  return next.toString();
}

/** Extract a valid action ID from a URL, or null. */
export function readActionFromUrl(url: URL): ActionableId | null {
  const raw = url.searchParams.get(DEEP_LINK_PARAM);
  if (!raw) return null;
  return isActionableId(raw) ? raw : null;
}

/**
 * Find the element matching the action ID, scroll it into view, pulse
 * the highlight class. No-op if no element matches.
 *
 * Callers should schedule this after the page has mounted (e.g., via
 * `requestAnimationFrame` or a short `setTimeout`) so `querySelector`
 * sees the post-mount DOM.
 */
export function highlightAction(actionId: ActionableId): boolean {
  if (typeof document === 'undefined') return false;

  const el = document.querySelector<HTMLElement>(`[data-action="${cssEscape(actionId)}"]`);
  if (!el) return false;

  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  el.classList.add('deep-link-highlight');

  // Remove the class after the animation ends so a second navigation
  // with the same actionId re-triggers the pulse.
  window.setTimeout(() => {
    el.classList.remove('deep-link-highlight');
  }, HIGHLIGHT_DURATION_MS);

  return true;
}

/**
 * Small CSS.escape polyfill for test environments where jsdom may not
 * expose it. Our IDs are always kebab-case lowercase so a simple escape
 * is sufficient in practice.
 */
function cssEscape(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }
  return value.replace(/[^a-zA-Z0-9\-_]/g, '\\$&');
}
