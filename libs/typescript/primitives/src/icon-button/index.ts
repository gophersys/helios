/**
 * `@eden/primitives` — the IconButton public surface.
 *
 * Re-exports the component and its token-derivation API. The component default export is the
 * Svelte 5 `icon-button.svelte`; the named exports are the pure token math (`deriveIconButtonTokens`,
 * `iconButtonStyleVars`) the design-correctness gate audits, plus the token type. The variant type
 * is the Button's (`ButtonVariant`) — one concept, one home: an IconButton is a Button shaped square.
 */
export { default as IconButton } from './icon-button.svelte';
export { deriveIconButtonTokens, iconButtonStyleVars, type IconButtonTokens } from './tokens.js';
