<script lang="ts">
  // The PROGRESS widget — a compact, LIVE read on the supervisor's run: turns + tool uses from the
  // meter, the lifecycle state, and the current activity, with a subtle activity affordance that
  // animates only while a turn is in flight. Every value updates the instant a new event folds into
  // the session. Fully token-driven from @eden/theme.
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import PanelWidget from './PanelWidget.svelte';

  let { session, theme }: { session: ChatSession; theme?: Theme } = $props();

  const turns = $derived(session.meter.turns);
  const toolUses = $derived(session.meter.toolUses);

  // A turn is in flight while the agent is actively working (thinking / responding / running a
  // tool). That drives the activity affordance's pulse and the state tone.
  const busy = $derived(
    session.activity === 'thinking' ||
      session.activity === 'responding' ||
      session.activity === 'tool',
  );

  // The lifecycle state as a scannable label; the raw token is exposed as a data attribute for tone.
  const stateLabel = $derived(session.sessionState.replace(/-/g, ' '));

  const tone = $derived.by(() => {
    if (session.sessionState === 'failed' || session.sessionState === 'aborted') return 'error';
    if (session.sessionState === 'completed') return 'done';
    if (busy) return 'busy';
    return 'idle';
  });

  // The activity readout mirrors the bottom status bar's verb, so the panel and the bar agree.
  const activityLabel = $derived.by(() => {
    switch (session.activity) {
      case 'thinking':
        return 'thinking';
      case 'responding':
        return 'responding';
      case 'tool':
        return session.activeTool ? `running ${session.activeTool}` : 'running tool';
      case 'done':
        return 'done';
      case 'failed':
        return 'failed';
      case 'stopped':
        return 'stopped';
      case 'connecting':
        return 'connecting';
      default:
        return 'idle';
    }
  });
</script>

<div class="progress" data-testid="progress-widget" data-tone={tone}>
  <PanelWidget title="Progress" {theme}>
    {#snippet children()}
      <dl class="progress__stats">
        <div class="stat" data-testid="progress-turns">
          <dt>turns</dt>
          <dd>{turns.toLocaleString()}</dd>
        </div>
        <div class="stat" data-testid="progress-tools">
          <dt>tools</dt>
          <dd>{toolUses.toLocaleString()}</dd>
        </div>
        <div class="stat stat--wide" data-testid="progress-state">
          <dt>state</dt>
          <dd class="stat__state" data-state={session.sessionState}>{stateLabel}</dd>
        </div>
      </dl>

      <div
        class="progress__bar"
        data-busy={busy}
        data-testid="progress-bar"
        role="img"
        aria-label={`agent ${activityLabel}`}
      >
        <span class="progress__fill" aria-hidden="true"></span>
      </div>
      <span class="progress__activity" data-testid="progress-activity">{activityLabel}</span>
    {/snippet}
  </PanelWidget>
</div>

<style>
  .progress {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-block-size: 0;
  }
  .progress__stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-1, 4px) var(--space-4, 16px);
    margin: 0;
  }
  .stat {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2, 8px);
    border-block-end: 1px dotted var(--eden-app-line);
    padding-block-end: var(--space-1, 4px);
  }
  .stat--wide {
    grid-column: 1 / -1;
  }
  .stat dt {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .stat dd {
    margin: 0;
    font-family: var(--font-code);
    font-size: var(--font-size-label, 13px);
    font-weight: 600;
    color: var(--eden-app-fg);
    font-variant-numeric: tabular-nums;
  }
  .stat__state {
    text-transform: capitalize;
  }
  .stat__state[data-state='failed'],
  .stat__state[data-state='aborted'] {
    color: var(--color-error);
  }
  .stat__state[data-state='completed'] {
    color: var(--color-info);
  }

  /* The activity affordance: a track that fills with an indeterminate sweep while busy, and rests
     as a calm filled bar when idle/terminal — a glanceable "alive and working" signal. */
  .progress__bar {
    position: relative;
    block-size: var(--space-1, 4px);
    border-radius: var(--eden-app-radius, 4px);
    background: var(--eden-app-line);
    overflow: hidden;
  }
  .progress__fill {
    position: absolute;
    inset-block: 0;
    inset-inline-start: 0;
    inline-size: 100%;
    background: var(--eden-app-muted);
    opacity: 0.5;
  }
  .progress__bar[data-busy='true'] .progress__fill {
    inline-size: 40%;
    opacity: 1;
    background: var(--eden-app-accent);
    animation: progress-sweep 1.4s ease-in-out infinite;
  }
  [data-tone='error'] .progress__fill {
    background: var(--color-error);
  }
  [data-tone='done'] .progress__fill {
    background: var(--color-info);
    opacity: 1;
  }
  .progress__activity {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    letter-spacing: 0.04em;
  }
  [data-tone='busy'] .progress__activity {
    color: var(--eden-app-accent);
  }
  [data-tone='error'] .progress__activity {
    color: var(--color-error);
  }
  @keyframes progress-sweep {
    0% {
      inset-inline-start: -40%;
    }
    100% {
      inset-inline-start: 100%;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .progress__bar[data-busy='true'] .progress__fill {
      animation: none;
      inline-size: 100%;
    }
  }
</style>
