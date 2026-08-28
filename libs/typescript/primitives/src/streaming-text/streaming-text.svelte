<!--
  @eden/primitives — StreamingText (ADR-0024 / RD-16). Renders assistant prose token-by-token with a
  blinking caret while the stream is live. The APPEARANCE is decided entirely by
  deriveStreamingTextTokens (streaming-text/tokens.ts) — every colour/size/space is a CSS custom
  property whose value is DERIVED from an @eden/theme token; this template references
  var(--eden-streaming-text-*) only and carries NO literal colour and NO literal px.

  Semantics: the prose lives in an aria-live="polite" region so a screen reader announces appended
  tokens without interrupting, and aria-busy reflects the streaming state. The caret is decorative
  (aria-hidden) and is hidden when the stream completes. The reveal math (appendChunk) is the host's
  to drive; this component renders the accumulated `text` and the live/done state it is handed.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { generateTheme, C21_SEED } from '@eden/theme';
  import { deriveStreamingTextTokens, streamingTextStyleVars } from './tokens.js';

  interface StreamingTextProps {
    /** The accumulated text revealed so far (the host drives the token-by-token append). */
    text?: string;
    /** Whether the stream is still arriving — drives the caret + aria-busy. */
    streaming?: boolean;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
  }

  let { text = '', streaming = true, theme }: StreamingTextProps = $props();

  const resolvedTheme = $derived(theme ?? generateTheme(C21_SEED));
  const tokens = $derived(deriveStreamingTextTokens(resolvedTheme));
  const styleVars = $derived(streamingTextStyleVars(tokens));
</script>

<div
  class="eden-streaming-text"
  data-eden-streaming-text=""
  data-streaming={streaming}
  role="status"
  aria-live="polite"
  aria-busy={streaming}
  style={styleVars}
>
  <span class="eden-streaming-text-prose">{text}</span>
  {#if streaming}
    <span class="eden-streaming-text-caret" aria-hidden="true"></span>
  {/if}
</div>

<style>
  .eden-streaming-text {
    color: var(--eden-streaming-text-fg);
    background: var(--eden-streaming-text-bg);
    font-family: var(--eden-streaming-text-font-family);
    font-size: var(--eden-streaming-text-font-size);
    line-height: var(--eden-streaming-text-line-height);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .eden-streaming-text-caret {
    display: inline-block;
    inline-size: var(--eden-streaming-text-caret-width);
    block-size: var(--eden-streaming-text-font-size);
    margin-inline-start: var(--eden-streaming-text-caret-width);
    background: var(--eden-streaming-text-caret);
    vertical-align: text-bottom;
    animation: eden-streaming-text-blink 1s steps(2, start) infinite;
  }

  @keyframes eden-streaming-text-blink {
    to {
      visibility: hidden;
    }
  }

  /* Respect reduced-motion: a steady caret, never a blink (WCAG 2.3.3 / prefers-reduced-motion). */
  @media (prefers-reduced-motion: reduce) {
    .eden-streaming-text-caret {
      animation: none;
    }
  }
</style>
