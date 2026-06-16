<script lang="ts">
  // An assistant turn: the agent's REASONING (ThinkingTrace — a distinct, expanded thinking box,
  // streamed live) above the answer (ChatMarkdown — the model's prose rendered as MARKDOWN in a
  // readable box: bold, code, lists, headings all formatted, with a streaming caret). The answer box
  // renders ONLY once there is text; while the agent is working with nothing to show yet, a small
  // pending pulse stands in (no empty caret box). Every colour/size derives from @eden/theme.
  import type { Theme } from '@eden/theme';
  import ThinkingTrace from './ThinkingTrace.svelte';
  import ChatMarkdown from './ChatMarkdown.svelte';

  let {
    text,
    thinking,
    streaming,
    theme,
  }: {
    text: string;
    thinking: string;
    streaming: boolean;
    theme: Theme;
  } = $props();
</script>

<div data-testid="assistant-message" data-streaming={streaming}>
  {#if thinking}
    <ThinkingTrace text={thinking} streaming={streaming && !text} {theme} />
  {/if}
  {#if text}
    <ChatMarkdown {text} {streaming} {theme} />
  {:else if streaming && !thinking}
    <!-- The agent has started but has nothing to show yet: a small pending pulse, NOT an empty
         answer box (the "empty assistant box" defect). -->
    <div class="pending" data-testid="assistant-pending" aria-label="working">
      <span class="pending__dot"></span>
      <span class="pending__dot"></span>
      <span class="pending__dot"></span>
    </div>
  {/if}
</div>

<style>
  .pending {
    display: inline-flex;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) 0;
  }
  .pending__dot {
    inline-size: 6px;
    block-size: 6px;
    border-radius: 50%;
    background: var(--eden-app-muted);
    animation: pending-bounce 1.2s ease-in-out infinite;
  }
  .pending__dot:nth-child(2) {
    animation-delay: 0.15s;
  }
  .pending__dot:nth-child(3) {
    animation-delay: 0.3s;
  }
  @keyframes pending-bounce {
    0%,
    60%,
    100% {
      opacity: 0.3;
      transform: translateY(0);
    }
    30% {
      opacity: 1;
      transform: translateY(-3px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pending__dot {
      animation: none;
    }
  }
</style>
