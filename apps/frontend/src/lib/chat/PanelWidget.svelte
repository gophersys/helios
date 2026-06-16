<script lang="ts">
  // PanelWidget — the collapsible container EVERY right-panel widget wraps its content in. The
  // "less is more" primitive: a titled section that MINIMIZES/MAXIMIZES (the user reveals context
  // only when they want it), with an optional count badge and an actions slot. Token-driven from
  // @eden/theme; the open state is local so each widget collapses independently.
  import type { Theme } from '@eden/theme';
  import type { Snippet } from 'svelte';

  let {
    title,
    count,
    defaultOpen = true,
    theme: _theme,
    children,
    actions,
  }: {
    title: string;
    count?: number | string;
    /** The INITIAL minimize/maximize state; the widget owns its expanded state thereafter. */
    defaultOpen?: boolean;
    theme?: Theme;
    children: Snippet;
    actions?: Snippet;
  } = $props();

  // svelte-ignore state_referenced_locally
  let expanded = $state(defaultOpen);
</script>

<section class="widget" data-testid="panel-widget" data-widget-title={title} data-open={expanded}>
  <header class="widget__head">
    <button
      class="widget__toggle"
      data-testid="panel-widget-toggle"
      aria-expanded={expanded}
      onclick={() => (expanded = !expanded)}
    >
      <span class="widget__chevron" data-open={expanded} aria-hidden="true">▸</span>
      <span class="widget__title">{title}</span>
      {#if count != null}<span class="widget__count">{count}</span>{/if}
    </button>
    {#if actions}<span class="widget__actions">{@render actions()}</span>{/if}
  </header>
  {#if expanded}
    <div class="widget__body" data-testid="panel-widget-body">{@render children()}</div>
  {/if}
</section>

<style>
  .widget {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-block-size: 0;
  }
  .widget__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2, 8px);
  }
  .widget__toggle {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: var(--eden-app-muted);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .widget__toggle:hover {
    color: var(--eden-app-fg);
  }
  .widget__chevron {
    transition: transform 160ms ease;
    color: var(--eden-app-accent);
  }
  .widget__chevron[data-open='true'] {
    transform: rotate(90deg);
  }
  .widget__count {
    color: var(--eden-app-accent);
    font-variant-numeric: tabular-nums;
  }
  .widget__actions {
    display: inline-flex;
    gap: var(--space-2, 8px);
  }
  .widget__body {
    display: flex;
    flex-direction: column;
    min-block-size: 0;
    animation: widget-open 180ms ease-out;
  }
  @keyframes widget-open {
    from {
      opacity: 0;
      transform: translateY(-3px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .widget__chevron,
    .widget__body {
      transition: none;
      animation: none;
    }
  }
</style>
