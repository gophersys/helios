<script lang="ts">
  // An assistant turn rendered on the design system: the @eden/primitives Message bubble
  // (role="assistant") wrapping the foldable ThinkingBlock (the reasoning) and the StreamingText
  // live token stream (the answer). The text accretes token-by-token from text-delta events and the
  // caret blinks until message-end (streaming=false). Every colour/size/space is derived from the
  // generated @eden/theme handed down — no hardcoded values.
  import { Message, StreamingText, ThinkingBlock } from '@eden/primitives';
  import type { Theme } from '@eden/theme';

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
  <Message role="assistant" {theme}>
    {#if thinking}
      <div class="thinking" data-testid="thinking-block">
        <ThinkingBlock summary="Thinking" open={false} {theme}>
          {thinking}
        </ThinkingBlock>
      </div>
    {/if}
    <div data-testid="assistant-text">
      <StreamingText text={revealed} {streaming} {theme} />
    </div>
  </Message>
</div>

<style>
  .thinking {
    margin-block-end: var(--space-3, 12px);
  }
</style>
