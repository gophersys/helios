<script lang="ts">
  // A tool-call card (REQ-0024 tool activity): renders a tool-start/update/end timeline entry
  // correlated by callId — the tool name, the grant it ran under, the redacted args summary, the
  // live partial digest (tool-update), and the final outcome + duration + result digest
  // (tool-end). The status drives the chip tone so a running / ok / error / denied call is
  // visually distinct.
  import type { ToolEntry } from '$lib/gateway/session.svelte';

  let { tool }: { tool: ToolEntry } = $props();

  const tone = $derived(
    tool.status === 'running'
      ? 'info'
      : tool.status === 'ok'
        ? 'ok'
        : tool.status === 'denied'
          ? 'muted'
          : 'warn',
  );
</script>

<article class="tool" data-testid="tool-card" data-status={tool.status}>
  <header class="tool__head">
    <span class="tool__icon" aria-hidden="true">⚙</span>
    <span class="tool__name">{tool.name}</span>
    {#if tool.isHostTool}
      <span class="chip chip--muted">host</span>
    {/if}
    <span class="chip chip--{tone}" data-testid="tool-status">{tool.status}</span>
    {#if tool.durationMs != null}
      <span class="tool__dur">{tool.durationMs}ms</span>
    {/if}
  </header>

  <dl class="tool__body">
    {#if tool.argsSummary}
      <div class="tool__row">
        <dt>args</dt>
        <dd><code>{tool.argsSummary}</code></dd>
      </div>
    {/if}
    {#if tool.grantId}
      <div class="tool__row">
        <dt>grant</dt>
        <dd><code>{tool.grantId}</code></dd>
      </div>
    {/if}
    {#if tool.partialDigest}
      <div class="tool__row">
        <dt>partial</dt>
        <dd><code>{tool.partialDigest}</code></dd>
      </div>
    {/if}
    {#if tool.resultDigest}
      <div class="tool__row">
        <dt>result</dt>
        <dd data-testid="tool-result"><code>{tool.resultDigest}</code></dd>
      </div>
    {/if}
  </dl>
</article>

<style>
  .tool {
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius);
    background: var(--codebg);
    padding: 0.7rem 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 78ch;
  }
  .tool__head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .tool__icon {
    color: var(--accent);
  }
  .tool__name {
    font-family: var(--font-code);
    font-weight: 650;
    font-size: 0.95rem;
  }
  .tool__dur {
    margin-left: auto;
    font-family: var(--font-code);
    font-size: var(--type-micro);
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .tool__body {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .tool__row {
    display: flex;
    gap: 0.6rem;
    align-items: baseline;
  }
  .tool__row dt {
    flex: none;
    width: 4.5rem;
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
  }
  .tool__row dd {
    margin: 0;
    min-width: 0;
    word-break: break-word;
  }
  .tool__row code {
    background: transparent;
    padding: 0;
    font-size: 0.85rem;
  }
</style>
