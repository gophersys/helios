<!--
  @eden/primitives — ToolCall (ADR-0024 / RD-16). A card surfacing one agent tool invocation: the
  tool name, its arguments (a code block), and a lifecycle status. The APPEARANCE is decided entirely
  by deriveToolCallTokens (tool-call/tokens.ts) — every colour/size/space is a CSS custom property
  whose value is DERIVED from an @eden/theme token; this template references var(--eden-tool-call-*)
  only and carries NO literal colour and NO literal px.

  Semantics: the card is a <section> labelled by its tool name. The status is conveyed by BOTH an
  accent colour AND a visible text label (never colour alone — WCAG 1.4.1), and the live status is an
  aria-live polite region so a screen reader hears the transition running→success/error. The args are
  a real <pre><code> block so assistive tech announces it as code.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { generateTheme, C21_SEED } from '@eden/theme';
  import { deriveToolCallTokens, toolCallStyleVars, type ToolCallStatus } from './tokens.js';

  interface ToolCallProps {
    /** The invoked tool's name (e.g. `read_file`). */
    tool: string;
    /** The serialised arguments to render in the code block. */
    args?: string;
    /** The lifecycle status — drives the status accent + label. */
    status?: ToolCallStatus;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
  }

  let { tool, args = '', status = 'running', theme }: ToolCallProps = $props();

  const resolvedTheme = $derived(theme ?? generateTheme(C21_SEED));
  const tokens = $derived(deriveToolCallTokens(status, resolvedTheme));
  const styleVars = $derived(toolCallStyleVars(tokens));
  const statusLabel = $derived(
    status === 'running' ? 'Running' : status === 'success' ? 'Succeeded' : 'Failed',
  );
</script>

<!-- role="group" (not a <section> landmark) — a tool-call card is grouped content, not a top-level
     page region; this keeps a chat log of many cards from flooding the a11y tree with landmarks. -->
<div
  class="eden-tool-call"
  data-eden-tool-call=""
  data-status={status}
  role="group"
  aria-label={`Tool call: ${tool}`}
  style={styleVars}
>
  <div class="eden-tool-call-head">
    <span class="eden-tool-call-tool">{tool}</span>
    <span class="eden-tool-call-status" role="status" aria-live="polite">{statusLabel}</span>
  </div>
  {#if args}
    <pre class="eden-tool-call-args"><code>{args}</code></pre>
  {/if}
</div>

<style>
  .eden-tool-call {
    display: flex;
    flex-direction: column;
    gap: var(--eden-tool-call-gap);
    box-sizing: border-box;
    padding: var(--eden-tool-call-padding);
    border-radius: var(--eden-tool-call-radius);
    color: var(--eden-tool-call-fg);
    background: var(--eden-tool-call-bg);
    border: 1px solid var(--eden-tool-call-border);
  }

  .eden-tool-call-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--eden-tool-call-gap);
    font-size: var(--eden-tool-call-title-size);
    line-height: var(--eden-tool-call-title-line-height);
    font-family: var(--eden-tool-call-title-family);
  }

  .eden-tool-call-tool {
    font-weight: 600;
  }

  /* The status text carries the state accent AND a word — colour is never the only signal. */
  .eden-tool-call-status {
    color: var(--eden-tool-call-status);
    font-weight: 600;
  }

  .eden-tool-call-args {
    margin: 0;
    font-size: var(--eden-tool-call-code-size);
    line-height: var(--eden-tool-call-code-line-height);
    font-family: var(--eden-tool-call-code-family);
    color: var(--eden-tool-call-fg);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .eden-tool-call-args code {
    font-family: inherit;
  }
</style>
