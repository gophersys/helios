/**
 * `@eden/primitives` — the Button public surface.
 *
 * Re-exports the component and its token-derivation API. The component default export is the
 * Svelte 5 `button.svelte`; the named exports are the pure token math (`deriveButtonTokens`,
 * `buttonStyleVars`, `defaultButtonTheme`) the design-correctness gate audits, plus the variant
 * and token types. One concept, one home — the appearance is decided in `tokens.ts`, cited here.
 */
export { default as Button } from './button.svelte';
export {
  deriveButtonTokens,
  buttonStyleVars,
  defaultButtonTheme,
  type ButtonVariant,
  type ButtonTokens,
  type ThemeSeed,
} from './tokens.js';
