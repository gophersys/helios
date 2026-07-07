<script lang="ts">
  // SETTINGS — a focused, dismissible surface for the workspace chat. "Less is more": only the
  // settings that are REAL and useful right now (color mode, density, the default harness). A modal
  // dialog over a scrim (role="dialog", aria-modal, Escape + close + scrim-click dismiss, the panel
  // takes focus on open). Token-driven from @eden/theme — every color/size is a var().
  //
  // Color mode: this control is now a thin view over the app-wide ThemeProvider store
  // (themePreference.svelte) — the ONE home for the light/dark/system choice (doc 17 §3). The store
  // persists to the 'eden-theme' key and reflects onto <html data-theme>; the +layout's CSS is
  // authored so that attribute switches the token block (light at :root+[data-theme='light'], dark
  // at [data-theme='dark'] and under the OS media query when no explicit light choice is set). The
  // panel keeps its user-visible 'System'/'Light'/'Dark' copy and its data-testids unchanged; it
  // just maps them to the store's lowercase preference. Density remains panel-local.
  import type { Theme } from '@eden/theme';
  import { themePreference, type ThemePreference } from '$lib/theme/themePreference.svelte';

  let { open = $bindable(false), theme: _theme }: { open?: boolean; theme?: Theme } = $props();

  type ColorMode = 'System' | 'Light' | 'Dark';
  type Density = 'Comfortable' | 'Compact';

  const COLOR_MODES: readonly ColorMode[] = ['System', 'Light', 'Dark'];
  const DENSITIES: readonly Density[] = ['Comfortable', 'Compact'];

  const DENSITY_KEY = 'eden.density';

  // The store speaks lowercase ('light'|'dark'|'system'); the panel's user-visible copy is
  // capitalized. These two helpers translate between the display label and the store value.
  const modeToPreference = (mode: ColorMode): ThemePreference =>
    mode.toLowerCase() as ThemePreference;
  const preferenceToMode = (preference: ThemePreference): ColorMode =>
    (preference.charAt(0).toUpperCase() + preference.slice(1)) as ColorMode;

  // The displayed color mode mirrors the store (reactive), so the active pill is correct on open.
  const colorMode = $derived<ColorMode>(preferenceToMode(themePreference.value));

  function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(key);
    return raw != null && (allowed as readonly string[]).includes(raw) ? (raw as T) : fallback;
  }

  // svelte-ignore state_referenced_locally
  let density = $state<Density>(readStored(DENSITY_KEY, DENSITIES, 'Comfortable'));

  let dialog = $state<HTMLDivElement | null>(null);

  function applyDensity(value: Density): void {
    if (typeof document === 'undefined') return;
    document.documentElement.setAttribute('data-density', value.toLowerCase());
  }

  function persist(key: string, value: string): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(key, value);
    } catch {
      /* storage may be unavailable (private mode / quota) — the live attribute still applies. */
    }
  }

  function chooseColorMode(mode: ColorMode): void {
    // Delegate to the app-wide store: it persists + reflects onto <html data-theme> in one step.
    themePreference.set(modeToPreference(mode));
  }

  function chooseDensity(value: Density): void {
    density = value;
    persist(DENSITY_KEY, value);
    applyDensity(value);
  }

  // Keep density applied while the panel exists — it owns reflecting that attribute onto <html>.
  // (Color mode is the store's job; the store reflects it on set + on the layout's mount.)
  $effect(() => {
    applyDensity(density);
  });

  // Focus the dialog when it opens so keyboard users land inside the surface; Escape then closes.
  $effect(() => {
    if (open && dialog) dialog.focus();
  });

  function close(): void {
    open = false;
  }

  function onScrimKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') close();
  }

  function onDialogKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.stopPropagation();
      close();
    }
  }
</script>

{#if open}
  <!-- scrim: click-out + Escape dismiss; role=presentation so it's not an extra landmark. -->
  <div
    class="scrim"
    role="presentation"
    data-testid="settings-scrim"
    onclick={close}
    onkeydown={onScrimKeydown}
  >
    <div
      class="panel"
      bind:this={dialog}
      role="dialog"
      tabindex="-1"
      aria-modal="true"
      aria-label="Workspace settings"
      data-testid="settings-panel"
      data-colormode={colorMode.toLowerCase()}
      data-density={density.toLowerCase()}
      onclick={(event) => event.stopPropagation()}
      onkeydown={onDialogKeydown}
    >
      <header class="panel__head">
        <div class="panel__heading">
          <p class="panel__eyebrow">Eden</p>
          <h2 class="panel__title">Settings</h2>
        </div>
        <button
          type="button"
          class="panel__close"
          data-testid="settings-close"
          aria-label="Close settings"
          onclick={close}
        >
          ✕
        </button>
      </header>

      <div class="panel__body">
        <!-- ── Color mode ─────────────────────────────────────────────────── -->
        <section class="field" data-testid="settings-colormode" aria-label="Color mode">
          <span class="field__label">Color mode</span>
          <div class="seg" role="radiogroup" aria-label="Color mode">
            {#each COLOR_MODES as mode (mode)}
              <button
                type="button"
                class="seg__opt"
                class:seg__opt--on={colorMode === mode}
                data-testid="settings-colormode-{mode.toLowerCase()}"
                role="radio"
                aria-checked={colorMode === mode}
                onclick={() => chooseColorMode(mode)}
              >
                {mode}
              </button>
            {/each}
          </div>
          <p class="field__hint">
            System follows your device's appearance{colorMode === 'System' ? ' (active).' : '.'}
          </p>
        </section>

        <!-- ── Density ────────────────────────────────────────────────────── -->
        <section class="field" data-testid="settings-density" aria-label="Density">
          <span class="field__label">Density</span>
          <div class="seg" role="radiogroup" aria-label="Density">
            {#each DENSITIES as value (value)}
              <button
                type="button"
                class="seg__opt"
                class:seg__opt--on={density === value}
                data-testid="settings-density-{value.toLowerCase()}"
                role="radio"
                aria-checked={density === value}
                onclick={() => chooseDensity(value)}
              >
                {value}
              </button>
            {/each}
          </div>
        </section>

        <!-- ── Harness (read-only) ────────────────────────────────────────── -->
        <section class="field" data-testid="settings-harness" aria-label="Default harness">
          <span class="field__label">Default harness</span>
          <div class="harness">
            <code class="harness__name" data-testid="settings-harness-value">claude</code>
            <span class="harness__note">more coming</span>
          </div>
        </section>
      </div>
    </div>
  </div>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal, 1000);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-4, 16px);
    background: color-mix(in oklab, var(--color-on-surface) 44%, transparent);
    animation: scrim-in 140ms ease-out;
  }
  .panel {
    inline-size: min(440px, 100%);
    max-block-size: min(86vh, 640px);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 20px);
    padding: var(--space-5, 20px);
    background: var(--eden-app-panel-bg);
    color: var(--eden-app-fg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    animation: panel-in 180ms ease-out;
  }
  .panel:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }
  .panel__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3, 12px);
  }
  .panel__eyebrow {
    margin: 0;
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }
  .panel__title {
    margin: 0;
    font-size: var(--font-size-title, 23px);
  }
  .panel__close {
    flex: none;
    inline-size: var(--space-7, 28px);
    block-size: var(--space-7, 28px);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 6px);
    color: var(--eden-app-muted);
    cursor: pointer;
    font-size: var(--font-size-label, 14px);
    transition:
      color 120ms ease,
      border-color 120ms ease;
  }
  .panel__close:hover {
    color: var(--eden-app-fg);
    border-color: var(--eden-app-accent);
  }
  .panel__close:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 1px;
  }
  .panel__body {
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 20px);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }
  .field__label {
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }
  .field__hint {
    margin: 0;
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
  }
  .seg {
    display: inline-flex;
    gap: var(--space-1, 4px);
    padding: var(--space-1, 4px);
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
  }
  .seg__opt {
    flex: 1;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: none;
    border: 1px solid transparent;
    border-radius: var(--eden-app-radius, 6px);
    color: var(--eden-app-muted);
    font-family: var(--font-code);
    font-size: var(--font-size-label, 14px);
    cursor: pointer;
    transition:
      color 120ms ease,
      background 120ms ease,
      border-color 120ms ease;
  }
  .seg__opt:hover {
    color: var(--eden-app-fg);
  }
  .seg__opt:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 1px;
  }
  .seg__opt--on {
    background: var(--eden-app-panel-bg);
    border-color: var(--eden-app-accent);
    color: var(--eden-app-fg);
  }
  .harness {
    display: inline-flex;
    align-items: center;
    gap: var(--space-3, 12px);
  }
  .harness__name {
    padding: var(--space-1, 4px) var(--space-3, 12px);
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 6px);
    font-family: var(--font-code);
    font-size: var(--font-size-label, 14px);
    color: var(--eden-app-fg);
  }
  .harness__note {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
  }
  @keyframes scrim-in {
    from {
      opacity: 0;
    }
  }
  @keyframes panel-in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .scrim,
    .panel {
      animation: none;
    }
    .seg__opt,
    .panel__close {
      transition: none;
    }
  }
</style>
