/**
 * `@eden/primitives` — the Badge public surface.
 *
 * Re-exports the component and its token-derivation API. The appearance is decided in `tokens.ts`
 * (which cites the shared surface-tokens/chat-surface vocabulary), cited here — one concept, one home.
 */
export { default as Badge } from './badge.svelte';
export {
  deriveBadgeTokens,
  badgeStyleVars,
  type BadgeVariant,
  type BadgeTokens,
} from './tokens.js';
