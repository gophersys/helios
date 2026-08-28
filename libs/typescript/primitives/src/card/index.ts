/**
 * `@eden/primitives` — the Card public surface.
 *
 * Re-exports the surface molecule and its token-derivation API. The appearance is decided in
 * `tokens.ts` (citing the shared surface-tokens/chat-surface vocabulary — the `surface` radius + the
 * `raised` shadow per doc 17 §4), cited here — one home.
 */
export { default as Card } from './card.svelte';
export { deriveCardTokens, cardStyleVars, type CardVariant, type CardTokens } from './tokens.js';
