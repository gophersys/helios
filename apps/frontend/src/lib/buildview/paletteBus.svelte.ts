// The command-palette BUS — the seam that makes ⌘K a SINGLE, globally-mounted palette (doc 17 §5,
// "the ⌘K palette goes global") while still letting the Build view contribute its live,
// session-scoped commands (new-project / settings / steer / abort / … + the Sessions jump list).
//
// One concept, one home: the palette itself is mounted ONCE in the (app) shell layout. Any surface
// that wants to add commands (today: the Build view) REGISTERS a provider on this bus at mount and
// clears it at destroy. The shell composes the always-on app-navigation group with whatever the
// active provider publishes, so the same ⌘K works from Projects, Sessions, Clusters — and, when a
// build is open, carries that build's controls too. The Build view's own "⌘K" affordance (the
// TopBar button) just calls `open()` on this bus, so there is exactly one palette element in the DOM.
import { getContext, setContext } from 'svelte';
import type { CommandPaletteGroup } from '@eden/primitives';

const KEY = Symbol('eden:palette-bus');

/** A palette provider: the groups a surface contributes + the dispatcher for their selection. */
export interface PaletteProvider {
  /** The command groups this surface contributes (reactive — read on every palette render). */
  groups: () => CommandPaletteGroup[];
  /** Dispatch a selected command value owned by this provider. Return true if it was handled. */
  run: (value: string) => boolean;
}

/** The shell-side palette controller the layout owns and the bus exposes. */
export class PaletteBus {
  /** Whether the single palette element is open. Bound by the shell's CommandPalette. */
  open = $state(false);
  /** The active provider (the Build view registers itself here while mounted). */
  #provider = $state<PaletteProvider | null>(null);

  /** The provider's live groups (empty when no build is open). Read by the shell. */
  get providerGroups(): CommandPaletteGroup[] {
    return this.#provider ? this.#provider.groups() : [];
  }

  /** Register a provider (the Build view calls this on mount). */
  register(provider: PaletteProvider): void {
    this.#provider = provider;
  }

  /** Clear a provider (the Build view calls this on destroy) — only if it is still the active one. */
  clear(provider: PaletteProvider): void {
    if (this.#provider === provider) this.#provider = null;
  }

  /** Toggle/open the palette (⌘K anywhere, or the TopBar affordance). */
  toggle(): void {
    this.open = !this.open;
  }
  show(): void {
    this.open = true;
  }

  /** Dispatch a selected command to the active provider; returns true if handled. */
  runProvider(value: string): boolean {
    return this.#provider ? this.#provider.run(value) : false;
  }
}

/** Provide the bus from the shell layout. */
export function provizePaletteBus(bus: PaletteBus): void {
  setContext(KEY, bus);
}

/** Read the bus from any descendant (the Build view). Null when rendered outside the shell. */
export function usePaletteBus(): PaletteBus | null {
  return getContext<PaletteBus | null>(KEY) ?? null;
}
