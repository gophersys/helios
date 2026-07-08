<script lang="ts">
  // A tool invocation rendered the TUI way (à la Claude Code): a status marker + the call
  // `Name(args)` on one line, and the result on a second line under an `⎿` L-connector — deliberate,
  // monospaced, status-coloured, not a plain card. Every colour/size derives from @eden/theme.
  import type { Theme } from '@eden/theme';
  import type { ToolEntry } from '$lib/gateway/session.svelte';

  let { tool, theme: _theme }: { tool: ToolEntry; theme?: Theme } = $props();

  const args = $derived(tool.argsSummary ?? '');
  const hasResult = $derived(
    tool.status === 'running' || tool.resultDigest != null || tool.durationMs != null,
  );
</script>

<div class="tool" data-testid="tool-card" data-status={tool.status}>
  <div class="tool__call">
    <span class="tool__marker" data-status={tool.status} aria-hidden="true">⏺</span>
    <span class="tool__name">{tool.name}</span>{#if args}<span class="tool__args">({args})</span
      >{/if}
    {#if tool.isHostTool}<span class="tool__tag">host</span>{/if}
    {#if tool.grantId}<span class="tool__tag" title="grant {tool.grantId}">grant</span>{/if}
  </div>
  {#if hasResult}
    <div class="tool__result" data-status={tool.status}>
      <span class="tool__connector" aria-hidden="true">⎿</span>
      <span class="tool__result-text" data-testid="tool-result">
        {#if tool.status === 'running' && tool.resultDigest == null}
          <span class="tool__running">running…</span>
        {:else if tool.resultDigest != null}{tool.resultDigest}{/if}
        {#if tool.partialDigest && tool.status === 'running'}{tool.partialDigest}{/if}
      </span>
      {#if tool.durationMs != null}<span class="tool__dur">{tool.durationMs}ms</span>{/if}
    </div>
  {/if}
</div>

<style>
  .tool {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    line-height: 1.5;
  }
  .tool__call {
    display: flex;
    align-items: baseline;
    gap: 4px;
    flex-wrap: wrap;
  }
  .tool__marker {
    color: var(--eden-app-muted);
    flex: none;
  }
  .tool__marker[data-status='running'] {
    color: var(--eden-app-accent);
    animation: tool-pulse 1.1s ease-in-out infinite;
  }
  .tool__marker[data-status='ok'] {
    color: var(--color-info);
  }
  .tool__marker[data-status='error'],
  .tool__marker[data-status='denied'] {
    color: var(--color-error);
  }
  .tool__name {
    color: var(--eden-app-fg);
    font-weight: 650;
  }
  .tool__args {
    color: var(--eden-app-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-inline-size: 48ch;
  }
  .tool__tag {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: 3px;
    padding: 0 4px;
  }
  /* the result, hung under an L-connector (the "connecting L line") */
  .tool__result {
    display: flex;
    align-items: baseline;
    gap: var(--space-2, 8px);
    padding-inline-start: 2px;
    color: color-mix(in oklab, var(--eden-app-fg) 70%, var(--eden-app-bg));
  }
  .tool__connector {
    color: var(--eden-app-line);
    flex: none;
  }
  .tool__result[data-status='error'] .tool__result-text,
  .tool__result[data-status='denied'] .tool__result-text {
    color: var(--color-error);
  }
  .tool__result-text {
    min-inline-size: 0;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
  }
  .tool__running {
    color: var(--eden-app-accent);
  }
  .tool__dur {
    flex: none;
    margin-inline-start: auto;
    color: var(--eden-app-muted);
    opacity: 0.8;
  }
  @keyframes tool-pulse {
    50% {
      opacity: 0.45;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .tool__marker[data-status='running'] {
      animation: none;
    }
  }
</style>
