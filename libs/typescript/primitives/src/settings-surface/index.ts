/**
 * `@eden/primitives` — the SettingsSurface public surface.
 *
 * Re-exports the sheet-hosted Settings organism (doc 17 §4 organisms / §7) and its token-derivation
 * API. The overlay BEHAVIOR (focus trap, Escape, scroll lock, focus return) is the bits-ui Dialog
 * layer the component composes — reinvented nowhere; the APPEARANCE + the two type voices (mono rail
 * label · sans section title) are decided in `tokens.ts` (citing the shared overlay + surface-tokens +
 * chat-surface vocabulary), cited here — one home.
 */
export { default as SettingsSurface } from './settings-surface.svelte';
export {
  deriveSettingsSurfaceTokens,
  settingsSurfaceStyleVars,
  type SettingsSurfaceTokens,
  type SettingsSection,
} from './tokens.js';
