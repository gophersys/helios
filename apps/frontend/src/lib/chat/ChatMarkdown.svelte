<script lang="ts">
  // ChatMarkdown — renders an agent's prose as MARKDOWN in a readable, token-driven box (bold,
  // italic, inline `code`, code blocks, lists, headings, links all render), reusing Eden's existing
  // markdown pipeline (lexMarkdown → the block-component dispatcher) rather than dumping raw text.
  // A blinking caret trails the content while the answer is still streaming. Reusable across any
  // agent surface that shows model output.
  import type { Theme } from '@eden/theme';
  import { lexMarkdown } from '$lib/markdown/tokens';
  import BlockList from '$lib/components/blocks/BlockList.svelte';

  let { text, streaming = false, theme: _theme }: { text: string; streaming?: boolean; theme?: Theme } =
    $props();

  // Re-lex the accreted text on each update; marked tolerates partial markdown (an unclosed **bold
  // renders literally until it closes), so streaming reads cleanly.
  const tokens = $derived(lexMarkdown(text));
</script>

<div class="answer" data-testid="assistant-text" data-streaming={streaming}>
  <div class="answer__body">
    <BlockList {tokens} />
    {#if streaming}<span class="answer__caret" aria-hidden="true"></span>{/if}
  </div>
</div>

<style>
  /* A soft, readable container set apart from the user bubble + the thinking box — the agent's
     answer, comfortable to read, with code/headings/lists properly styled by the block components. */
  .answer {
    color: var(--eden-app-fg);
    background: color-mix(in oklab, var(--eden-app-fg) 3%, var(--eden-app-bg));
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 6px);
    padding: var(--space-3, 12px) var(--space-4, 16px);
    font-size: var(--font-size-label, 14px);
    line-height: 1.62;
  }
  .answer__body {
    min-inline-size: 0;
  }
  /* Chat-tighten the block rhythm (the document renderer is airier than a chat bubble wants). */
  .answer :global(> .answer__body > :first-child) {
    margin-block-start: 0;
  }
  .answer :global(p) {
    margin-block: var(--space-2, 8px);
  }
  .answer :global(ul),
  .answer :global(ol) {
    margin-block: var(--space-2, 8px);
    padding-inline-start: var(--space-5, 20px);
  }
  .answer :global(h1),
  .answer :global(h2),
  .answer :global(h3),
  .answer :global(h4) {
    margin-block: var(--space-3, 12px) var(--space-2, 8px);
    line-height: 1.3;
  }
  .answer :global(code) {
    font-family: var(--font-code);
    font-size: 0.92em;
    background: color-mix(in oklab, var(--eden-app-accent) 12%, var(--eden-app-bg));
    border-radius: 3px;
    padding: 0.05em 0.35em;
  }
  .answer :global(pre code) {
    background: none;
    padding: 0;
  }
  .answer :global(strong) {
    color: var(--eden-app-fg);
    font-weight: 680;
  }
  .answer :global(a) {
    color: var(--eden-app-accent);
    text-underline-offset: 2px;
  }
  /* the trailing streaming caret */
  .answer__caret {
    display: inline-block;
    inline-size: 0.5ch;
    block-size: 1em;
    margin-inline-start: 2px;
    vertical-align: text-bottom;
    background: var(--eden-app-accent);
    animation: answer-blink 1s steps(2, start) infinite;
  }
  @keyframes answer-blink {
    to {
      visibility: hidden;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .answer__caret {
      animation: none;
    }
  }
</style>
