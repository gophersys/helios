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
  /* The card is a shadcn Card — a --card surface, a 1px --border hairline, --radius-lg geometry, and
     the refined --shadow ramp (resting xs → hover md). All tokens derive from @eden/theme (via the
     +layout.svelte SHADCN SKIN MAPPING). */
  .card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2, 8px);
    inline-size: 100%;
    min-block-size: 7.5rem;
    padding: var(--space-5, 20px);
    text-align: start;
    background: var(--card);
    color: var(--card-foreground);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-xs);
    cursor: pointer;
    font-family: inherit;
    transition:
      transform var(--duration-short-3, 160ms) var(--ease-standard, ease),
      border-color var(--duration-short-3, 160ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-3, 160ms) var(--ease-standard, ease);
  }
  /* The shadcn hover lift — a small translate, a --border-strong edge, and the --shadow-md ramp
     step. Focus-visible mirrors the lift so keyboard users get the same affordance. */
  .card:hover {
    transform: translateY(-2px);
    border-color: var(--border-strong);
    box-shadow: var(--shadow-md);
  }
  .card:focus-visible {
    outline: 2px solid var(--ring);
    outline-offset: 2px;
  }
  .card:active {
    transform: translateY(0);
  }

  .card__name {
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--card-foreground);
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
    color: var(--muted-foreground);
  }
  .card__dot {
    inline-size: 7px;
    block-size: 7px;
    border-radius: 50%;
    flex: none;
    background: var(--muted-foreground);
    /* A soft halo so the status dot reads as a live indicator, not a period. */
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--muted-foreground) 16%, transparent);
  }
  .card__dot[data-tone='active'] {
    background: var(--color-info);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--color-info) 18%, transparent);
  }
  .card__dot[data-tone='busy'] {
    background: var(--primary);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--primary) 20%, transparent);
    animation: card-pulse 1.4s ease-in-out infinite;
  }
  .card__dot[data-tone='error'] {
    background: var(--destructive);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--destructive) 18%, transparent);
  }
  .card__status[data-tone='busy'] .card__status-text {
    color: var(--primary);
  }
  .card__status[data-tone='error'] .card__status-text {
    color: var(--destructive);
  }

  .card__meta {
    font-size: var(--font-size-caption, 12px);
    color: var(--muted-foreground);
    overflow-wrap: anywhere;
  }

  .card__stacks {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1, 4px);
    margin-block-start: auto;
    padding-block-start: var(--space-1, 4px);
  }
  /* Shadcn "outline" badges — a --muted fill, a 1px --border, --radius-sm corners, mono micro-label. */
  .card__chip {
    display: inline-flex;
    align-items: center;
    padding: 2px var(--space-2, 8px);
    border-radius: var(--radius-sm);
    background: var(--surface-muted);
    border: 1px solid var(--border);
    color: var(--muted-foreground);
    font-family: var(--font-code);
    font-size: 11px;
    line-height: 1.5;
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
