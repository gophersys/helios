/**
 * `@eden/primitives` — the Tabs public surface.
 *
 * Re-exports the segmented view-switcher (bits-ui behavior + Eden tokens) and its token-derivation
 * API. The appearance is decided in `tokens.ts` (citing the shared chat-surface vocabulary), cited
 * here — one home.
 */
export { default as Tabs } from './tabs.svelte';
export { deriveTabsTokens, tabsStyleVars, type Tab, type TabsTokens } from './tokens.js';
