/**
 * `@eden/primitives` — the EmptyState public surface.
 *
 * Re-exports the empty-state product surface and its token-derivation API. The appearance + the two
 * type voices are decided in `tokens.ts` (citing the shared chat-surface vocabulary), cited here —
 * one home.
 */
export { default as EmptyState } from './empty-state.svelte';
export { deriveEmptyStateTokens, emptyStateStyleVars, type EmptyStateTokens } from './tokens.js';
