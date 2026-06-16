<script lang="ts">
  // An assistant turn: the agent's REASONING (ThinkingTrace — a distinct, expanded thinking box,
  // shown live) above the answer (the @eden/primitives Message bubble + StreamingText token stream).
  // The answer text accretes token-by-token and is typewriter-smoothed; the bubble renders ONLY once
  // there is text (no empty caret box), and while the agent is still working with nothing to show a
  // small pending indicator stands in. Every colour/size/space derives from @eden/theme.
  import { StreamingText } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import ThinkingTrace from './ThinkingTrace.svelte';

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

  // Typewriter smoothing (the host-side reveal StreamingText defers to us): the backend streams
  // text in CHUNKS (claude flushes several tokens per delta), so reveal the accumulated text
  // character-by-character toward the target — chunked deltas read as smooth, continuous typing.
  // A larger backlog catches up faster (never lags far behind); when the stream ends we snap to the
  // full text so nothing is ever withheld. Driven by a TIMER (not requestAnimationFrame, which a
  // headless/background page pauses — that would withhold the text entirely). The effect tracks
  // `text`/`streaming` synchronously and reads `revealed` only inside the timer (untracked), so a
  // new delta restarts the catch-up without a re-run storm.
  let revealed = $state('');
  $effect(() => {
    const target = text;
    if (!streaming) {
      revealed = target;
      return;
    }
    if (revealed.length > target.length) revealed = target; // a reused bubble shrank — resync.
    const id = setInterval(() => {
      if (revealed.length >= target.length) {
        clearInterval(id);
        return;
      }
      const remaining = target.length - revealed.length;
      const step = Math.max(1, Math.ceil(remaining / 8));
      revealed = target.slice(0, revealed.length + step);
    }, 16);
    return () => clearInterval(id);
  });
</script>

<div data-testid="assistant-message" data-streaming={streaming}>
  {#if thinking}
    <ThinkingTrace text={thinking} streaming={streaming && !revealed} {theme} />
  {/if}
  {#if revealed}
    <!-- The agent's answer reads as clean prose under its timeline node (no heavy bubble — the user
         turn is the distinct bubble); the streaming caret lives in StreamingText. -->
    <div class="answer" data-testid="assistant-text">
      <StreamingText text={revealed} {streaming} {theme} />
    </div>
  {:else if streaming && !thinking}
    <!-- The agent has started but has nothing to show yet: a small pending pulse, NOT an empty
         answer box with a blinking caret (the "empty assistant box" defect). -->
    <div class="pending" data-testid="assistant-pending" aria-label="working">
      <span class="pending__dot"></span>
      <span class="pending__dot"></span>
      <span class="pending__dot"></span>
    </div>
  {/if}
</div>

<style>
  .answer {
    color: var(--eden-app-fg);
    line-height: 1.6;
  }
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
