/**
 * `@eden/primitives` — the WizardShell public surface.
 *
 * Re-exports the full-screen wizard focus organism (doc 17 §6) and its token-derivation API. The
 * appearance + the three type voices (mono eyebrow/counter · serif display title · sans lead) are
 * decided in `tokens.ts` (citing the shared chat-surface + surface-tokens vocabulary), cited here —
 * one home. `wizardProgressFraction` is the ONE progress-fraction home the shell + its tests read.
 */
export { default as WizardShell } from './wizard-shell.svelte';
export {
  deriveWizardShellTokens,
  wizardShellStyleVars,
  wizardProgressFraction,
  type WizardShellTokens,
  type WizardStep,
} from './tokens.js';
