<script lang="ts">
  // The bottom STATUS BAR — a JS representation of the harness TUI (à la Claude Code's status
  // line). It turns the live agent activity into a spinner + verb + running thinking-token count +
  // elapsed clock, so a long silent think (the `thinking_tokens` heartbeat phase) is never a dead
  // screen. Every colour/size/space is a generated @eden/theme token — no hardcoded values.
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import type { Activity } from '$lib/gateway/types';
  import type { Theme } from '@eden/theme';

  let { session }: { session: ChatSession; theme?: Theme } = $props();

  // A ticking clock while a turn is live, for the elapsed readout. The interval is torn down the
  // moment the turn ends (turnStartedAt → null), so it is leak-free and idle when nothing runs.
  let now = $state(Date.now());
  $effect(() => {
    if (session.turnStartedAt === null) return;
    now = Date.now();
    const id = setInterval(() => (now = Date.now()), 200);
    return () => clearInterval(id);
  });

  // While the SSE is still connecting and no turn has started, the bar reads "Connecting…".
  const activity = $derived<Activity>(
    session.activity === 'idle' && session.connection !== 'open' && !session.terminal
      ? 'connecting'
      : session.activity,
  );
  const busy = $derived(
    activity === 'thinking' || activity === 'responding' || activity === 'tool',
  );
  const elapsedMs = $derived(session.turnStartedAt ? Math.max(0, now - session.turnStartedAt) : 0);

  function formatElapsed(ms: number): string {
    const total = Math.floor(ms / 1000);
    const m = Math.floor(total / 60);
    const s = total % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  }

  const label = $derived.by(() => {
    switch (activity) {
      case 'connecting':
        return 'Connecting…';
      case 'thinking':
        return 'Thinking…';
      case 'responding':
        return 'Responding…';
      case 'tool':
        return `Running ${session.activeTool ?? 'tool'}…`;
      case 'done':
        return 'Done';
      case 'failed':
        return 'Failed';
      case 'stopped':
        return 'Stopped';
      default:
        return 'Ready';
    }
  });

  // The thinking-token chip shows while thinking, and as a "thought for N" summary after a turn
  // that did any reasoning — mirroring Claude Code surfacing the reasoning cost.
  const showTokens = $derived(
    session.thinkingTokens > 0 && (activity === 'thinking' || activity === 'done'),
  );
  const tone = $derived(
    activity === 'failed' ? 'error' : activity === 'stopped' ? 'warning' : 'accent',
  );
</script>

<div
  class="statusbar"
  data-testid="agent-status"
  data-activity={activity}
  data-busy={busy}
  data-thinking-tokens={session.thinkingTokens}
  data-tone={tone}
  role="status"
  aria-live="polite"
>
  <span class="statusbar__spinner" class:statusbar__spinner--on={busy} aria-hidden="true"></span>
  <span class="statusbar__label" data-testid="agent-status-label">{label}</span>
  {#if showTokens}
    <span class="statusbar__sep" aria-hidden="true">·</span>
    <span class="statusbar__tokens" data-testid="agent-status-tokens">
      {session.thinkingTokens.toLocaleString()} thinking tokens
    </span>
  {/if}
  {#if busy}
    <span class="statusbar__sep" aria-hidden="true">·</span>
    <span class="statusbar__elapsed" data-testid="agent-status-elapsed"
      >{formatElapsed(elapsedMs)}</span
    >
    <span class="statusbar__hint">esc to interrupt</span>
  {/if}
</div>

<style>
  .statusbar {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border-block-start: 1px solid var(--eden-app-line);
    background: var(--eden-app-panel-bg);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    min-block-size: calc(var(--space-6, 24px) + var(--space-2, 8px));
  }

  /* The spinner: a token-tinted ring that rotates only while the agent is busy (otherwise a calm
     dot), so the bar reads "alive and working" at a glance — the TUI cursor analogue. */
  .statusbar__spinner {
    inline-size: var(--space-3, 12px);
    block-size: var(--space-3, 12px);
    border-radius: 50%;
    background: var(--eden-app-muted);
    flex: none;
  }
  .statusbar__spinner--on {
    background: transparent;
    border: 2px solid color-mix(in oklab, var(--eden-app-accent) 30%, transparent);
    border-block-start-color: var(--eden-app-accent);
    animation: statusbar-spin 0.7s linear infinite;
  }
  .statusbar__label {
    color: var(--eden-app-fg);
    font-weight: 600;
  }
  [data-tone='error'] .statusbar__label {
    color: var(--color-error);
  }
  [data-tone='warning'] .statusbar__label {
    color: var(--color-warning);
  }
  .statusbar__sep {
    opacity: 0.5;
  }
  .statusbar__tokens {
    color: var(--eden-app-accent);
  }
  .statusbar__elapsed {
    font-variant-numeric: tabular-nums;
  }
  .statusbar__hint {
    margin-inline-start: auto;
    opacity: 0.6;
    letter-spacing: 0.04em;
  }

  @keyframes statusbar-spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .statusbar__spinner--on {
      animation-duration: 2s;
    }
  }
</style>
