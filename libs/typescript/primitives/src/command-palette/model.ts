/**
 * `@eden/primitives` — CommandPalette data model (ADR-0024, the component contract).
 *
 * The grouped command model the palette renders + fuzzy-filters. These are pure data-shape types (no
 * logic, no tokens) — they live in their own `.ts` module so BOTH the component (`*.svelte`) and the
 * public barrel (`index.ts`) cite ONE home (10 §9), and so the published type surface is emitted by
 * `tsc` directly (a named type re-exported FROM a `*.svelte` file is not resolvable by the strict
 * `tsc --noEmit` typecheck through the `*.svelte` ambient module — the model lives here instead).
 */

/** One selectable command in the palette. The `value` is the stable filter/selection key. */
export interface CommandPaletteItem {
  /** The stable unique value used for filtering, ranking, and selection (bind:value reads this). */
  readonly value: string;
  /** The visible label rendered for the item (also the default fuzzy-match text). */
  readonly label: string;
  /** Extra keywords folded into the fuzzy match (so "new doc" can match a "Create file" command). */
  readonly keywords?: readonly string[];
  /** Whether the item is non-selectable (forwarded to the bits-ui Command.Item disabled semantics). */
  readonly disabled?: boolean;
}

/** One labelled group of commands — rendered as a role=group with a role-labelled heading. */
export interface CommandPaletteGroup {
  /** A stable unique value for the group (the bits-ui Command.Group key). */
  readonly value: string;
  /** The visible group heading (role=presentation heading; labels the group for screen readers). */
  readonly heading: string;
  /** The commands in this group. */
  readonly items: readonly CommandPaletteItem[];
}
