<script lang="ts">
  // The DECISIONS widget — the architecture DECISIONS the ARCHITECT agent recorded (ADRs and
  // decision records), derived LIVE from the session's tool-call stream. We reuse deriveArtifacts
  // (one home for path parsing) and keep only the artifacts whose file name reads like a decision
  // record: an ADR (adr-0001, ADR1, 0001-…) or anything ending .adr or carrying "decision". Each is
  // a decision entry: the file name as the decision title + a status dot. Secondary context, so it
  // starts MINIMIZED (defaultOpen={false}). Token-driven from @eden/theme.
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import { deriveArtifacts } from '$lib/workspace/agentWorkspace';
  import PanelWidget from './PanelWidget.svelte';

  let { session, theme }: { session: ChatSession; theme?: Theme } = $props();

  const ADR_NAME = /(^|\/)(adr-?\d|\d{4}-)/i;

  function isDecision(path: string): boolean {
    const p = path.toLowerCase();
    return ADR_NAME.test(p) || p.endsWith('.adr') || p.includes('decision');
  }

  const decisions = $derived(deriveArtifacts(session.entries).filter((a) => isDecision(a.path)));

  function fileName(path: string): string {
    const parts = path.split('/');
    return parts[parts.length - 1] || path;
  }
</script>

<div
  class="decisions"
  data-testid="decisions-widget"
  data-count={decisions.length}
  aria-label="architecture decisions"
>
  <PanelWidget title="Decisions" count={decisions.length} defaultOpen={false} {theme}>
    {#snippet children()}
      {#if decisions.length === 0}
        <p class="decisions__empty" data-testid="decisions-empty">
          No decisions yet — recorded ADRs appear here as the architect writes them.
        </p>
      {:else}
        <ul class="decisions__list" role="list">
          {#each decisions as decision (decision.path)}
            <li
              class="decision"
              data-testid="decision-row"
              data-status={decision.status}
              data-path={decision.path}
            >
              <span class="decision__dot" data-status={decision.status} aria-hidden="true"></span>
              <span class="decision__title">{fileName(decision.path)}</span>
            </li>
          {/each}
        </ul>
      {/if}
    {/snippet}
  </PanelWidget>
</div>

<style>
  .decisions {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-block-size: 0;
  }
  .decisions__empty {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    margin: 0;
  }
  .decisions__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .decision {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    border-radius: var(--eden-app-radius, 4px);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    animation: decision-in 240ms ease-out;
  }
  .decision:hover {
    background: var(--eden-app-panel-bg);
  }
  .decision__dot {
    inline-size: 7px;
    block-size: 7px;
    border-radius: 50%;
    flex: none;
    background: var(--eden-app-muted);
  }
  .decision__dot[data-status='running'] {
    background: var(--eden-app-accent);
    animation: decision-pulse 1.2s ease-in-out infinite;
  }
  .decision__dot[data-status='ok'] {
    background: var(--color-info);
  }
  .decision__dot[data-status='error'],
  .decision__dot[data-status='denied'] {
    background: var(--color-error);
  }
  .decision__title {
    color: var(--eden-app-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-inline-size: 0;
  }
  @keyframes decision-in {
    from {
      opacity: 0;
      transform: translateY(-3px);
    }
  }
  @keyframes decision-pulse {
    50% {
      opacity: 0.4;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .decision {
      animation: none;
    }
    .decision__dot[data-status='running'] {
      animation: none;
    }
  }
</style>
