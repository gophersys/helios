/**
 * `@eden/primitives` — the Divider public surface.
 *
 * Re-exports the rule atom and its token-derivation API. The appearance (colour + inset) is decided
 * in `tokens.ts` (citing the shared chat-surface vocabulary), cited here — one home.
 */
export { default as Divider } from './divider.svelte';
export {
  deriveDividerTokens,
  dividerStyleVars,
  type DividerOrientation,
  type DividerTokens,
} from './tokens.js';
