<script lang="ts">
  // A tool-call timeline entry on the design system: the @eden/primitives ToolCall card (tool name
  // + args summary + lifecycle status accent), with the agent-loop detail (the grant it ran under,
  // the redacted result digest, the duration) surfaced beneath it. The status drives the primitive's
  // gated accent; everything is token-driven off the generated @eden/theme — no hardcoded colour.
  import { ToolCall, type ToolCallStatus } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import type { ToolEntry } from '$lib/gateway/session.svelte';

  let { tool, theme }: { tool: ToolEntry; theme: Theme } = $props();

  // Map the session's four-state lifecycle onto the primitive's three-state status: a denied tool
  // is a failed invocation (error accent), an ok tool succeeded. `running` and `error` pass through.
  const status = $derived<ToolCallStatus>(
    tool.status === 'ok' ? 'success' : tool.status === 'running' ? 'running' : 'error',
  );
  const args = $derived(tool.argsSummary ?? '');
</script>

<div data-testid="tool-card" data-status={tool.status}>
  <ToolCall tool={tool.name} {args} {status} {theme} />
  {#if tool.grantId || tool.resultDigest || tool.durationMs != null || tool.isHostTool}
    <dl class="detail">
      {#if tool.isHostTool}
        <div class="detail__row">
          <dt>kind</dt>
          <dd><code>host tool</code></dd>
        </div>
      {/if}
      {#if tool.grantId}
        <div class="detail__row">
          <dt>grant</dt>
          <dd><code>{tool.grantId}</code></dd>
        </div>
      {/if}
      {#if tool.resultDigest}
        <div class="detail__row">
          <dt>result</dt>
          <dd data-testid="tool-result"><code>{tool.resultDigest}</code></dd>
        </div>
      {/if}
      {#if tool.durationMs != null}
        <div class="detail__row">
          <dt>took</dt>
          <dd><code>{tool.durationMs}ms</code></dd>
        </div>
      {/if}
    </dl>
  {/if}
</div>

<style>
  .detail {
    margin: var(--space-1, 4px) 0 0;
    padding-inline-start: var(--space-3, 12px);
    display: flex;
    flex-direction: column;
    gap: var(--space-1, 4px);
  }
  .detail__row {
    display: flex;
    gap: var(--space-3, 12px);
    align-items: baseline;
  }
  .detail__row dt {
    flex: none;
    inline-size: 4rem;
    font-size: var(--font-size-caption, 12px);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: color-mix(in oklab, var(--color-on-surface) 58%, var(--color-surface));
  }
  .detail__row dd {
    margin: 0;
    min-width: 0;
    word-break: break-word;
  }
  .detail__row code {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
  }
</style>
