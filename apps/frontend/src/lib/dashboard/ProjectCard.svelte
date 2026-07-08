<script lang="ts" module>
  // ProjectSummary — the SHAPE a card needs to render one project tile. It is intentionally a thin,
  // display-only view: the Projects dashboard maps the gateway's persisted ProjectViews onto this, so
  // the card stays decoupled from the gateway value layer. Everything past `id`/`name` is optional so
  // a half-known record still renders cleanly. `sessionId` is the build session the card opens into.
  export interface ProjectSummary {
    id: string;
    name: string;
    kind?: string;
    status?: string;
    harness?: string;
    updatedAt?: string;
    stacks?: string[];
    sessionId?: string;
  }
</script>

<script lang="ts">
  // ProjectCard — one project tile in the Projects dashboard grid. A clickable card surfacing the
  // project NAME prominently, a status dot + status text, a muted kind/harness line, and stack chips.
  // Pure presentation: clean props in (`project`), an `onOpen` event out — no network, no stores, no
  // $lib/gateway value imports. A subtle hover lift invites the click; the whole tile is one <button>
  // so keyboard + pointer activation are identical and free.
  //
  // Token-driven from @eden/theme: every colour/size/space is a var() over the allowed app token
  // vocabulary (--eden-app-*, --space-*, --font-size-*, --font-code, --color-*). The only literals are
  // var() fallbacks + hairline border widths. Reduced-motion is honored.
  import type { Theme } from '@eden/theme';

  let {
    project,
    onOpen,
    // `theme` is accepted so a host can hand the active generated theme to this card uniformly with
    // every other Eden component; the visual tokens resolve from the @eden/theme cascade on the page,
    // so the prop is a forward-compatible seam (referenced to satisfy noUnusedLocals) rather than read
    // per-property here.
    theme: _theme,
  }: { project: ProjectSummary; onOpen?: () => void; theme?: Theme } = $props();

  // Map a free-form status string onto one of a few visual tones so the dot/text colour reads at a
  // glance. Unknown / absent statuses fall back to the neutral "idle" tone (a muted dot).
  const tone = $derived.by<'active' | 'busy' | 'error' | 'idle'>(() => {
    const status = (project.status ?? '').toLowerCase();
    if (status === 'error' || status === 'failed' || status === 'denied') return 'error';
    if (status === 'running' || status === 'building' || status === 'busy' || status === 'thinking')
      return 'busy';
    if (status === 'active' || status === 'ready' || status === 'ok' || status === 'open')
      return 'active';
    return 'idle';
  });

  const statusLabel = $derived((project.status ?? '').trim() || 'idle');

  // The muted secondary line: "kind · harness", dropping either half when absent so it never reads
  // as a dangling separator. Empty when neither is known (the line is then hidden).
  const metaLine = $derived(
    [project.kind, project.harness]
      .map((part) => (part ?? '').trim())
      .filter(Boolean)
      .join(' · '),
  );

  const stacks = $derived((project.stacks ?? []).filter((stack) => stack.trim().length > 0));

  function open(): void {
    onOpen?.();
  }
</script>

<button
  type="button"
  class="card"
  data-testid="project-card"
  data-project-id={project.id}
  data-tone={tone}
  aria-label={`Open project ${project.name}`}
  onclick={open}
>
  <span class="card__name" data-testid="project-card-name">{project.name}</span>

  <span class="card__status" data-testid="project-card-status" data-tone={tone}>
    <span class="card__dot" data-tone={tone} aria-hidden="true"></span>
    <span class="card__status-text">{statusLabel}</span>
  </span>

  {#if metaLine}
    <span class="card__meta" data-testid="project-card-meta">{metaLine}</span>
  {/if}

  {#if stacks.length > 0}
    <span class="card__stacks" data-testid="project-card-stacks" role="list">
      {#each stacks as stack (stack)}
        <span class="card__chip" data-testid="project-card-chip" role="listitem">{stack}</span>
      {/each}
    </span>
  {/if}
</button>

<style>
  .card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2, 8px);
    inline-size: 100%;
    padding: var(--space-4, 16px);
    text-align: start;
    background: var(--eden-app-panel-bg);
    color: var(--eden-app-fg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    cursor: pointer;
    font-family: inherit;
    /* W5: the hover lift rides the theme motion tokens (nearest ladder step + standard easing). */
    transition:
      transform var(--duration-short-3, 160ms) var(--ease-standard, ease),
      border-color var(--duration-short-3, 160ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-3, 160ms) var(--ease-standard, ease);
  }
  /* The subtle hover lift — a small translate + tinted border + shadow that reads "clickable" without
     shouting. Focus-visible mirrors the lift so keyboard users get the same affordance. */
  .card:hover {
    transform: translateY(-2px);
    border-color: color-mix(in oklab, var(--eden-app-accent) 60%, var(--eden-app-line));
    box-shadow: 0 8px 24px color-mix(in oklab, var(--color-on-surface) 14%, transparent);
  }
  .card:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }
  .card:active {
    transform: translateY(0);
  }

  .card__name {
    font-size: var(--font-size-body-large, 16px);
    font-weight: 600;
    color: var(--eden-app-fg);
    line-height: 1.25;
    overflow-wrap: anywhere;
  }

  .card__status {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }
  .card__dot {
    inline-size: 8px;
    block-size: 8px;
    border-radius: 50%;
    flex: none;
    background: var(--eden-app-muted);
  }
  .card__dot[data-tone='active'] {
    background: var(--color-info);
  }
  .card__dot[data-tone='busy'] {
    background: var(--eden-app-accent);
    animation: card-pulse 1.4s ease-in-out infinite;
  }
  .card__dot[data-tone='error'] {
    background: var(--color-error);
  }
  .card__status[data-tone='busy'] .card__status-text {
    color: var(--eden-app-accent);
  }
  .card__status[data-tone='error'] .card__status-text {
    color: var(--color-error);
  }

  .card__meta {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    overflow-wrap: anywhere;
  }

  .card__stacks {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1, 4px);
    margin-block-start: var(--space-1, 4px);
  }
  .card__chip {
    display: inline-flex;
    align-items: center;
    padding: 2px var(--space-2, 8px);
    border-radius: var(--eden-app-radius, 6px);
    background: color-mix(in oklab, var(--eden-app-accent) 12%, transparent);
    color: color-mix(in oklab, var(--eden-app-accent) 80%, var(--eden-app-fg));
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    line-height: 1.4;
  }

  @keyframes card-pulse {
    50% {
      opacity: 0.4;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .card {
      transition: none;
    }
    .card:hover {
      transform: none;
    }
    .card__dot[data-tone='busy'] {
      animation: none;
    }
  }
</style>
