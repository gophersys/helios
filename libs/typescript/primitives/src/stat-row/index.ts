/**
 * `@eden/primitives` — the StatRow public surface.
 *
 * Re-exports the Clusters number-row molecule and its token-derivation API. The appearance is decided
 * in `tokens.ts` (citing the shared chat-surface vocabulary + the mono family), cited here — one home.
 */
export { default as StatRow } from './stat-row.svelte';
export { deriveStatRowTokens, statRowStyleVars, type Stat, type StatRowTokens } from './tokens.js';
