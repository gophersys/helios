<script lang="ts">
  // An assistant message bubble (REQ-0024 streamed assistant text + foldable thinking). The text
  // accretes token-by-token from text-delta events; the thinking block accretes from
  // thinking-delta events and is foldable (collapsed by default) so reasoning is distinct from
  // the answer. A streaming bubble shows a live caret until message-end.
  import { marked } from 'marked';

  let {
    text,
    thinking,
    streaming,
  }: {
    text: string;
    thinking: string;
    streaming: boolean;
  } = $props();

  // marked is configured synchronously (no async extensions), so parse returns a string.
  const html = $derived(text ? (marked.parse(text, { async: false }) as string) : '');
</script>

<div class="bubble bubble--assistant" data-testid="assistant-message" class:streaming>
  <div class="bubble__role">
    <span class="dot" aria-hidden="true"></span>
    assistant
  </div>

  {#if thinking}
    <details class="thinking" data-testid="thinking-block">
      <summary>thinking</summary>
      <p class="thinking__text">{thinking}</p>
    </details>
  {/if}

  <!-- eslint-disable-next-line svelte/no-at-html-tags -->
  <div class="bubble__text" data-testid="assistant-text">
    {@html html}{#if streaming}<span class="caret" aria-hidden="true"></span>{/if}
  </div>
</div>

<style>
  .bubble {
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
    max-width: 78ch;
    background: var(--panel-bg);
    border: 1px solid var(--panel-line);
  }
  .bubble__role {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-family: var(--font-code);
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin-bottom: 0.4rem;
  }
  .dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: var(--accent);
  }
  .bubble__text {
    line-height: 1.6;
  }
  .bubble__text :global(p) {
    margin: 0 0 0.6rem;
  }
  .bubble__text :global(p:last-child) {
    margin-bottom: 0;
  }
  .bubble__text :global(pre) {
    background: var(--codebg);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 0.7rem 0.9rem;
    overflow-x: auto;
  }
  .thinking {
    margin-bottom: 0.5rem;
    border-left: 2px solid var(--line);
    padding-left: 0.7rem;
  }
  .thinking summary {
    cursor: pointer;
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    font-family: var(--font-code);
  }
  .thinking__text {
    margin: 0.4rem 0 0;
    font-style: italic;
    color: var(--muted);
    font-size: 0.92rem;
  }
  .caret {
    display: inline-block;
    width: 0.5rem;
    height: 1.05em;
    margin-left: 1px;
    vertical-align: text-bottom;
    background: var(--accent);
    animation: blink 1s step-end infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0;
    }
  }
</style>
