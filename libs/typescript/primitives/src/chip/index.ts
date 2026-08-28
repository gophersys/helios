/**
 * `@eden/primitives` — the Chip public surface.
 *
 * Re-exports the mono data chip and its token-derivation API. The appearance is decided in
 * `tokens.ts` (citing the shared surface-tokens/chat-surface vocabulary), cited here — one home.
 */
export { default as Chip } from './chip.svelte';
export {
  deriveChipTokens,
  chipStyleVars,
  MONO_FONT_FAMILY,
  type ChipVariant,
  type ChipTokens,
} from './tokens.js';
