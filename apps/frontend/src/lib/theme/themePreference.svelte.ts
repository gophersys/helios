// The theme-preference store — the single home for the user's light/dark/system choice (doc 17
// §3: "the app mounts a ThemeProvider (persisted preference: light/dark/system)"). It owns three
// things and nothing else:
//
//   1. the reactive `preference` value ('light' | 'dark' | 'system'),
//   2. its persistence to localStorage under the 'eden-theme' key, and
//   3. reflecting it onto <html data-theme> — 'light'/'dark' set the attribute, 'system' REMOVES
//      it (so the +layout's prefers-color-scheme block takes over, matching the OS).
//
// The CSS emission (in +layout.svelte) is authored so the attribute is the switch: light tokens
// live at :root AND html[data-theme='light']; dark tokens live at html[data-theme='dark'] AND
// (via the media query, scoped to html:not([data-theme='light'])) whenever the OS is dark and no
// explicit light choice is present. So 'system' = no attribute = OS-driven, exactly as before.
//
// The FIRST paint is handled by the tiny inline script in app.html (it reads localStorage and sets
// data-theme before hydration) to avoid a flash-of-wrong-theme; this store is the reactive/runtime
// authority once the app is alive.

import { browser } from '$app/environment';

/** The three preference states. 'system' defers to the OS via prefers-color-scheme. */
export type ThemePreference = 'light' | 'dark' | 'system';

/** The RESOLVED mode — the concrete surface the tokens paint (system collapses to the OS choice). A
 *  surface that hands a generated Theme OBJECT to @eden/primitives (not just the CSS cascade) reads
 *  this to pick the light/dark Theme, so the component chrome flips WITH the app (doc 17 §3). */
export type ResolvedMode = 'light' | 'dark';

/** The localStorage key the inline app.html bootstrap and this store share. One name, one home. */
export const THEME_STORAGE_KEY = 'eden-theme';

const VALID: readonly ThemePreference[] = ['light', 'dark', 'system'];

function isPreference(value: unknown): value is ThemePreference {
  return typeof value === 'string' && (VALID as readonly string[]).includes(value);
}

/** Read the persisted preference, defaulting to 'system' when unset/unreadable/invalid. */
function readStored(): ThemePreference {
  if (!browser) return 'system';
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(raw) ? raw : 'system';
  } catch {
    return 'system';
  }
}

/** Reflect a preference onto <html data-theme>: set it for light/dark, remove it for system. */
function applyToDocument(preference: ThemePreference): void {
  if (!browser) return;
  const root = document.documentElement;
  if (preference === 'system') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', preference);
  }
}

/**
 * The theme store — a Svelte 5 rune-backed singleton. `.value` is the reactive preference; setting
 * it persists to localStorage and reflects onto <html> in one step. Components read `store.value`
 * inside markup/effects to stay reactive; call `store.set(...)` to change the mode.
 */
class ThemeStore {
  // svelte-ignore state_referenced_locally — the initial read is intentional (hydration seed).
  #preference = $state<ThemePreference>(readStored());
  // The live OS dark-mode signal (reactive), tracked so `resolvedMode` re-derives when the OS flips
  // and the preference is 'system'. Seeded from matchMedia on mount; a listener keeps it current.
  #osDark = $state<boolean>(false);

  constructor() {
    if (browser && typeof window.matchMedia === 'function') {
      const mql = window.matchMedia('(prefers-color-scheme: dark)');
      this.#osDark = mql.matches;
      // A change listener keeps the resolved mode live when the OS theme flips under 'system'.
      mql.addEventListener('change', (e) => {
        this.#osDark = e.matches;
      });
    }
  }

  /** The current preference (reactive). */
  get value(): ThemePreference {
    return this.#preference;
  }

  /** The RESOLVED concrete mode (reactive): light/dark pass through; 'system' collapses to the live OS
   *  choice. A surface handing a Theme OBJECT to @eden/primitives reads this to flip the component
   *  chrome WITH the app (the sheet/overlay tokens are derived from the passed Theme, not the cascade). */
  get resolvedMode(): ResolvedMode {
    if (this.#preference === 'system') return this.#osDark ? 'dark' : 'light';
    return this.#preference;
  }

  /** Choose a mode: update the reactive value, persist it, and reflect it onto <html>. */
  set(preference: ThemePreference): void {
    this.#preference = preference;
    if (browser) {
      try {
        localStorage.setItem(THEME_STORAGE_KEY, preference);
      } catch {
        /* storage unavailable (private mode / quota) — the live attribute still applies below. */
      }
    }
    applyToDocument(preference);
  }

  /**
   * Reconcile the DOM attribute with the persisted preference. Called on mount so the store's
   * runtime authority matches whatever the inline bootstrap set (they read the same key, so this
   * is normally a no-op — but it guarantees the invariant if the two ever diverge).
   */
  sync(): void {
    applyToDocument(this.#preference);
  }
}

/** The app-wide theme preference. One instance; every surface reads/writes the same choice. */
export const themePreference = new ThemeStore();
