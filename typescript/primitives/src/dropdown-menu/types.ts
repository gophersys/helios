/**
 * `@eden/primitives` — the DropdownMenu data contract.
 *
 * A menu's rows are DATA, not arbitrary markup, so the component takes a typed `items` array. The
 * type lives here in a `.ts` (not inside the `.svelte` script) so it is a first-class named export
 * of the module surface — tsc and `svelte-package` both see it, the `.apibaseline` freezes it, and
 * the `.svelte` component imports it (one concept, one home — 10 §9).
 */

/** One menu row — a label and its activation handler (the data a menu is built from). */
export interface DropdownMenuItem {
  /** The visible, accessible item label. */
  readonly label: string;
  /** The activation handler (fired by bits-ui on click, Enter, or Space). */
  readonly onSelect: () => void;
  /** Disabled rows are present but not operable (excluded from keyboard activation). */
  readonly disabled?: boolean;
}
