/**
 * `@eden/primitives` — the CommandPalette public surface.
 *
 * Re-exports the component and its token-derivation API. The component default export is the Svelte
 * 5 `command-palette.svelte` (the OD-1 ⌘K: Dialog.Portal wrapping Command.Root, on bits-ui@2.18.1);
 * the named exports are the pure token math (`deriveCommandPaletteTokens`,
 * `commandPaletteStyleVars`, `defaultCommandPaletteTheme`, `commandContrast`) the design-correctness
 * gate audits, plus the model + token types. One concept, one home — the appearance is decided in
 * `tokens.ts`, cited here; the model types are declared on the component, cited here.
 */
export { default as CommandPalette } from './command-palette.svelte';
export type { CommandPaletteItem, CommandPaletteGroup } from './model.js';
export {
  deriveCommandPaletteTokens,
  commandPaletteStyleVars,
  defaultCommandPaletteTheme,
  commandContrast,
  type CommandPaletteTokens,
  type ThemeSeed,
} from './tokens.js';
