<script lang="ts">
  // ThinkingTrace — the agent's REASONING shown live, expanded, in a distinct tinted box (a global
  // part of the agent framework: any agent surface renders its thinking here). Unlike a folded
  // reasoning block, it is OPEN by default — you watch the agent think — and is visually separated
  // from the answer by an accent rule + a muted, italic, monospaced treatment. Collapsible
  // (minimize/maximize) so a long trace can be tucked away. Auto-scrolls to the latest reasoning as
  // it streams. Fully token-driven from @eden/theme.
  import type { Theme } from '@eden/theme';

  let {
    text,
    streaming = false,
    theme: _theme,
  }: { text: string; streaming?: boolean; theme?: Theme } = $props();

  let expanded = $state(true);
  let scroller = $state<HTMLElement | null>(null);

  // Keep the latest reasoning in view as it streams (only while expanded + streaming).
  $effect(() => {
    if (streaming && expanded && text && scroller) {
      const el = scroller;
      queueMicrotask(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  });
</script>

<section
  class="thinking"
  data-testid="thinking-block"
  data-streaming={streaming}
  data-open={expanded}
>
  <button class="thinking__head" aria-expanded={expanded} onclick={() => (expanded = !expanded)}>
    <span class="thinking__glyph" class:thinking__glyph--live={streaming} aria-hidden="true">✦</span
    >
    <span class="thinking__label">Thinking{streaming ? '…' : ''}</span>
    <span class="thinking__chevron" data-open={expanded} aria-hidden="true">▸</span>
  </button>
  {#if expanded}
    <div class="thinking__body" bind:this={scroller} data-testid="thinking-content">{text}</div>
  {/if}
</section>

<style>
  /* A distinct REASONING box: accent-tinted surface + an accent left rule, set apart from the
     answer. Muted, italic, monospaced — visibly "the agent thinking", not the final reply. */
  .thinking {
    border-inline-start: 2px solid color-mix(in oklab, var(--eden-app-accent) 55%, transparent);
    background: color-mix(in oklab, var(--eden-app-accent) 6%, var(--eden-app-bg));
    border-radius: var(--eden-app-radius, 4px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    margin-block-end: var(--space-3, 12px);
  }
  .thinking__head {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    inline-size: 100%;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: var(--eden-app-accent);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .thinking__glyph--live {
    animation: thinking-spin 1.6s linear infinite;
    display: inline-block;
  }
  .thinking__label {
    flex: 1;
    text-align: start;
  }
  .thinking__chevron {
    transition: transform 160ms ease;
  }
  .thinking__chevron[data-open='true'] {
    transform: rotate(90deg);
  }
  .thinking__body {
    margin-block-start: var(--space-2, 8px);
    color: color-mix(in oklab, var(--eden-app-fg) 78%, var(--eden-app-bg));
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    line-height: 1.55;
    font-style: italic;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    max-block-size: 18rem;
    overflow-y: auto;
  }
  @keyframes thinking-spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .thinking__glyph--live {
      animation: none;
    }
    .thinking__chevron {
      transition: none;
    }
  }
</style>
