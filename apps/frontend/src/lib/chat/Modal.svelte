<script lang="ts">
  // Modal — the ONE HOME for centered overlays in the chat workspace: a reusable, global, square-ish
  // centered dialog shell that BOTH the product wizard AND future detail/session views adopt. It owns
  // the centered-overlay concept (scrim + centered panel) so no view re-spells it.
  //
  // Behavior mirrors the a11y of ProductWizard / SettingsPanel exactly: role="dialog", aria-modal,
  // aria-label (the title), Escape closes, scrim click-out closes, the panel takes focus on open, and
  // a close ✕ control flips `open` to false. Controlled via the `open` bindable — the host owns the
  // open state; the shell only renders + dismisses.
  //
  // This is a PURE shell: clean props in, `open` bindable out, content via snippets. No app-specific
  // coupling, no network, no $lib/gateway value imports. The body content (children) and an optional
  // footer are the caller's — the wizard/detail views re-home their inner markup here unchanged.
  //
  // Token-driven from @eden/theme: every color/size/space is a var() over the allowed app token
  // vocabulary (--eden-app-*, --space-*, --font-size-*, --font-code, --color-*, --z-modal). The only
  // literals are var() fallbacks + the hairline border widths. Reduced-motion is honored.
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';

  let {
    open = $bindable(false),
    title,
    size = 'md',
    // `theme` is accepted so a host can hand the active generated theme to this shell uniformly with
    // every other chat component; the visual tokens resolve from the @eden/theme cascade on the page,
    // so the prop is a forward-compatible seam (referenced to satisfy noUnusedLocals) rather than read
    // per-property here.
    theme: _theme,
    children,
    footer,
  }: {
    open?: boolean;
    title: string;
    size?: 'sm' | 'md' | 'lg';
    theme?: Theme;
    children: Snippet;
    footer?: Snippet;
  } = $props();

  let panel = $state<HTMLDivElement | null>(null);

  // Focus the panel when it opens so keyboard users land inside the surface; Escape then closes.
  $effect(() => {
    if (open && panel) panel.focus();
  });

  function close(): void {
    open = false;
  }

  function onScrimKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') close();
  }

  function onPanelKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.stopPropagation();
      close();
    }
  }
</script>

{#if open}
  <!-- scrim: click-out + Escape dismiss; role=presentation so it is not an extra landmark. -->
  <div
    class="scrim"
    role="presentation"
    data-testid="modal-scrim"
    onclick={close}
    onkeydown={onScrimKeydown}
  >
    <div
      class="panel"
      bind:this={panel}
      role="dialog"
      tabindex="-1"
      aria-modal="true"
      aria-label={title}
      data-testid="modal"
      data-size={size}
      onclick={(event) => event.stopPropagation()}
      onkeydown={onPanelKeydown}
    >
      <header class="panel__head">
        <h2 class="panel__title" data-testid="modal-title">{title}</h2>
        <button
          type="button"
          class="panel__close"
          data-testid="modal-close"
          aria-label="Close"
          onclick={close}
        >
          ✕
        </button>
      </header>

      <div class="panel__body" data-testid="modal-body">
        {@render children()}
      </div>

      {#if footer}
        <footer class="panel__footer" data-testid="modal-footer">
          {@render footer()}
        </footer>
      {/if}
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
  /* Square-ish centered panel sized by `size`: sm ~420px, md ~560px, lg ~760px. Caps at the viewport
     so it never overflows; the body scrolls under a ~80vh ceiling so the header/footer stay pinned. */
  .panel {
    --modal-inline: 560px;
    inline-size: min(var(--modal-inline), 100%);
    max-block-size: min(80vh, 760px);
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    padding: var(--space-5, 20px);
    background: var(--eden-app-panel-bg);
    color: var(--eden-app-fg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    box-shadow: 0 12px 40px color-mix(in oklab, var(--color-on-surface) 18%, transparent);
    animation: panel-in 180ms ease-out;
  }
  .panel[data-size='sm'] {
    --modal-inline: 420px;
  }
  .panel[data-size='md'] {
    --modal-inline: 560px;
  }
  .panel[data-size='lg'] {
    --modal-inline: 760px;
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
    flex: none;
  }
  .panel__title {
    margin: 0;
    font-size: var(--font-size-title, 23px);
    color: var(--eden-app-fg);
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
  /* The scrolling region — header + footer stay pinned, only the body scrolls under the 80vh cap. */
  .panel__body {
    flex: 1 1 auto;
    min-block-size: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }
  .panel__footer {
    flex: none;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-3, 12px);
    padding-block-start: var(--space-2, 8px);
    border-block-start: 1px solid var(--eden-app-line);
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
    .panel__close {
      transition: none;
    }
  }
</style>
