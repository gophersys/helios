/**
 * `@eden/primitives` — the Kbd public surface.
 *
 * Re-exports the key-cap component and its token-derivation API. The appearance is decided in
 * `tokens.ts` (citing the shared surface-tokens/chat-surface vocabulary), cited here — one home.
 */
export { default as Kbd } from './kbd.svelte';
export { deriveKbdTokens, kbdStyleVars, type KbdTokens } from './tokens.js';
