/**
 * Deep-link action registry.
 *
 * Every right-clickable UI element must use an ID from this list. The
 * literal-union type enforces this at compile time — adding a
 * `use:actionable={{ id: 'typo' }}` would fail `svelte-check`.
 *
 * URL format: `<page-path>?a=<actionId>`
 *
 * When a user opens a deep link, the layout effect finds the element
 * with `data-action="<actionId>"` on the loaded page, scrolls it into
 * view, and pulses it. Other URL state (tab, revision, filters) stays
 * in its own existing query params.
 *
 * Adding a new action:
 *   1. Add a new ID to ACTIONABLE_IDS below (alphabetical within group).
 *   2. Add `use:actionable={{ id: 'your-id', label: 'Human Readable' }}`
 *      to the target element.
 *
 * Removing an action:
 *   - Remove from this list AND from every `use:actionable` referencing
 *     it (TypeScript will point them out).
 */

export const ACTIONABLE_IDS = [
  // ── Products list / creation ────────────────────────────────
  'new-product',

  // ── Product detail header / tabs ───────────────────────────
  'edit-product',
  'tab-overview',
  'tab-hardware',
  'tab-assets',
  'tab-manufacturing',
  'tab-stages',
  'tab-fixtures',

  // ── Product · Hardware tab ─────────────────────────────────
  'sync-from-repo',
  'add-revision',
  'activate-revision',
  'archive-revision',
  'delete-revision',
  'edit-revision',

  // ── Product · Assets tab ───────────────────────────────────
  'upload-fw',
  'upload-modem-fw',
  'download-asset-set',
  'delete-asset-set',
  'delete-modem-fw',

  // ── Product · Stages (Validation) tab ──────────────────────
  'configure-stage',
  'trigger-build',

  // ── Product · Manufacturing tab ────────────────────────────
  'configure-mfg-stage',
  'disable-mfg-stage',

  // ── Manufacturing sessions ─────────────────────────────────
  'new-session',
  'scan-panel',
  'scan-standalone',
  'end-session',

  // ── Validation runs ────────────────────────────────────────
  'cancel-run',
  'retrigger-run',
  'compare-runs',

  // ── Fixtures ───────────────────────────────────────────────
  'create-fixture',
  'delete-fixture',
  'assign-slot',

  // ── Users / Admin ──────────────────────────────────────────
  'add-user',
  'deactivate-user',
  'create-permission-set',

  // ── Settings ───────────────────────────────────────────────
  'create-api-key',

  // ── Builds / CI ────────────────────────────────────────────
  'retrigger-build',
] as const;

export type ActionableId = (typeof ACTIONABLE_IDS)[number];

const ACTIONABLE_ID_SET = new Set<string>(ACTIONABLE_IDS);

/** Runtime guard — used by the layout effect to validate `?a=` params. */
export function isActionableId(value: string): value is ActionableId {
  return ACTIONABLE_ID_SET.has(value);
}
