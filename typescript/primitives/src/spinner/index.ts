/**
 * `@eden/primitives` — the Spinner public surface.
 *
 * Re-exports the loading atom and its token-derivation API. The appearance + motion are decided in
 * `tokens.ts` (citing the shared surface-tokens/chat-surface vocabulary + the theme motion tokens),
 * cited here — one home.
 */
export { default as Spinner } from './spinner.svelte';
export {
  deriveSpinnerTokens,
  spinnerStyleVars,
  type SpinnerVariant,
  type SpinnerTokens,
} from './tokens.js';
