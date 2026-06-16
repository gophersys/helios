<script lang="ts">
  // SETTINGS — a focused, dismissible surface for the workspace chat. "Less is more": only the
  // settings that are REAL and useful right now (color mode, density, the default harness). A modal
  // dialog over a scrim (role="dialog", aria-modal, Escape + close + scrim-click dismiss, the panel
  // takes focus on open). Token-driven from @eden/theme — every color/size is a var().
  //
  // Color mode: the +layout emits the dark token block ONLY under @media (prefers-color-scheme:
  // dark), so an explicit Light/Dark choice can't be expressed by the layout alone. We honour the
  // user's choice by writing data-theme on <html> and injecting an override stylesheet built from
  // the SAME generated token blocks (edenLight/DarkCss) — math is still the one source, we just
  // re-scope it under [data-theme='…']. 'System' clears the attribute and falls back to the media
  // query the layout already ships.
  import type { Theme } from '@eden/theme';
  import { edenLightCss, edenDarkCss } from '$lib/theme/edenTheme';

  let { open = $bindable(false), theme: _theme }: { open?: boolean; theme?: Theme } = $props();

  type ColorMode = 'System' | 'Light' | 'Dark';
  type Density = 'Comfortable' | 'Compact';

  const COLOR_MODES: readonly ColorMode[] = ['System', 'Light', 'Dark'];
  const DENSITIES: readonly Density[] = ['Comfortable', 'Compact'];

  const COLORMODE_KEY = 'eden.colormode';
  const DENSITY_KEY = 'eden.density';

  // The override stylesheet that makes an explicit Light/Dark choice win over the layout's
  // prefers-color-scheme block. Injected once, lazily; data-theme on <html> activates a block.
  const OVERRIDE_STYLE_ID = 'eden-colormode-override';
  const overrideCss = `:root[data-theme='light']{${edenLightCss.replace(/^:root\s*\{|\}\s*$/g, '')}}
:root[data-theme='dark']{${edenDarkCss.replace(/^:root\s*\{|\}\s*$/g, '')}}`;

  function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(key);
    return raw != null && (allowed as readonly string[]).includes(raw) ? (raw as T) : fallback;
  }

  // svelte-ignore state_referenced_locally
  let colorMode = $state<ColorMode>(readStored(COLORMODE_KEY, COLOR_MODES, 'System'));
  // svelte-ignore state_referenced_locally
  let density = $state<Density>(readStored(DENSITY_KEY, DENSITIES, 'Comfortable'));

  let dialog = $state<HTMLDivElement | null>(null);

  function ensureOverrideStyle(): void {
    if (typeof document === 'undefined') return;
    if (document.getElementById(OVERRIDE_STYLE_ID)) return;
    const el = document.createElement('style');
    el.id = OVERRIDE_STYLE_ID;
    el.textContent = overrideCss;
    document.head.appendChild(el);
  }

  function applyColorMode(mode: ColorMode): void {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    if (mode === 'System') {
      root.removeAttribute('data-theme');
      root.classList.remove('dark');
      return;
    }
    ensureOverrideStyle();
    root.setAttribute('data-theme', mode.toLowerCase());
    root.classList.toggle('dark', mode === 'Dark');
  }

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
    colorMode = mode;
    persist(COLORMODE_KEY, mode);
    applyColorMode(mode);
  }

  function chooseDensity(value: Density): void {
    density = value;
    persist(DENSITY_KEY, value);
    applyDensity(value);
  }

  // Apply persisted preferences on mount (and keep them applied if they change) — the panel is the
  // one home for these attributes, so it owns reflecting them onto <html> the moment it exists.
  $effect(() => {
    applyColorMode(colorMode);
  });
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
