/**
 * `@eden/primitives` — the UsageMeter public surface. One concept, one home — the appearance and the
 * meter math are decided in `tokens.ts`, cited here.
 */
export { default as UsageMeter } from './usage-meter.svelte';
export {
  deriveUsageMeterTokens,
  usageMeterStyleVars,
  usageFraction,
  usageTier,
  barWidthPercent,
  type UsageTier,
  type UsageMeterTokens,
} from './tokens.js';
