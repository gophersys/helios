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
      <StreamingText {text} {streaming} {theme} />
    </div>
  </Message>
</div>

<style>
  .thinking {
    margin-block-end: var(--space-3, 12px);
  }
</style>
