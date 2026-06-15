/**
 * `@eden/primitives` — the PermissionRequest public surface. One concept, one home — the appearance is
 * decided in `tokens.ts`, cited here; the action affordances delegate to the Button primitive.
 */
export { default as PermissionRequest } from './permission-request.svelte';
export {
  derivePermissionRequestTokens,
  permissionRequestStyleVars,
  permissionHeadingPairOklch,
  type PermissionRequestTokens,
} from './tokens.js';
