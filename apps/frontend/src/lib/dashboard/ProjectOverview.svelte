<script lang="ts">
  // ProjectOverview — the project spine's Overview (doc 17 §5: status · coordinates · activity). The
  // project's home surface once it is past provisioning: a status Badge (mapped onto the Clusters
  // health vocabulary via @eden/primitives), the coordinates (repo path/branch/session id as MONO
  // data, P-D4), and an activity/summary Card carrying a StatRow of the project's key numbers. Fully
  // reusable + token-driven: it composes @eden/primitives (Badge, Card, StatRow, Chip) and reads the
  // app's --eden-app-* / --color-* vocabulary — no hand-set hex/px on a painted role.
  import type { Theme } from '@eden/theme';
  import { Badge, Card, StatRow, Chip, type Stat, type BadgeVariant } from '@eden/primitives';
  import type { ProjectStatus, ProjectView } from '$lib/gateway/types';

  let { project, theme }: { project: ProjectView; theme?: Theme } = $props();

  // Map a ProjectStatus onto the Badge's health vocabulary (the Clusters triple-encoding: a role
  // colour + a WORD — never colour alone). `building`/ready → updating (in motion), terminal-ok →
  // healthy, failed → down, the provisioning steps → updating, draft → unknown.
  function statusVariant(status: ProjectStatus): BadgeVariant {
    switch (status) {
      case 'failed':
        return 'down';
      case 'building':
      case 'supervisor_ready':
      case 'wizard':
        return 'healthy';
      case 'draft':
        return 'unknown';
      default:
        return 'updating';
    }
  }
  const statusLabel = $derived(project.status.replace(/_/g, ' '));

  // The activity/summary numbers — a real StatRow of the project's key counts (stacks/services and the
  // SDLC-phase-ish coordinates the view carries). Only real fields; no fabricated metrics.
  const stats = $derived<Stat[]>([
    { label: 'kind', value: project.kind },
    { label: 'stacks', value: String(project.stacks.length) },
    { label: 'services', value: String(project.services.length) },
    { label: 'harness', value: project.harness },
  ]);

  const sessionId = $derived(project.supervisorAgentId || project.sessionId || '');
  function relativeTime(iso?: string): string {
    if (!iso) return '—';
    const then = Date.parse(iso);
    if (Number.isNaN(then)) return '—';
    const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.round(hours / 24)}d ago`;
  }
</script>

<div class="overview" data-testid="project-overview">
  <!-- IDENTITY + STATUS — the project name (serif identity moment via the page title elsewhere) and a
       health Badge conveying its lifecycle state. -->
  <header class="overview__head">
    <div class="overview__title">
      <h1 class="overview__name" data-testid="overview-name">{project.name}</h1>
      <span data-testid="overview-status">
        <Badge variant={statusVariant(project.status)} status {theme}>
          {statusLabel}
        </Badge>
      </span>
    </div>
    {#if project.idea}
      <p class="overview__idea" data-testid="overview-idea">{project.idea}</p>
    {/if}
  </header>

  <!-- ACTIVITY / SUMMARY — a Card carrying the project's key numbers as a StatRow. -->
  <Card variant="raised" {theme} aria-label="Project summary">
    {#snippet header()}
      <strong class="card__title">Summary</strong>
    {/snippet}
    {#snippet body()}
      <StatRow {stats} {theme} />
      {#if project.stacks.length > 0}
        <ul class="chips" role="list" data-testid="overview-stacks">
          {#each project.stacks as stack (stack)}
            <li><Chip {theme}>{stack}</Chip></li>
          {/each}
        </ul>
      {/if}
    {/snippet}
    {#snippet footer()}
      <span class="card__foot">Updated {relativeTime(project.updatedAt)}</span>
    {/snippet}
  </Card>

  <!-- COORDINATES — the repo/branch/session id as MONO data (P-D4). -->
  <Card variant="flat" {theme} aria-label="Project coordinates">
    {#snippet header()}
      <strong class="card__title">Coordinates</strong>
    {/snippet}
    {#snippet body()}
      <dl class="coords" data-testid="overview-coordinates">
        <dt>Repository</dt>
        <dd>
          {#if project.repoUrl}
            <a class="mono link" href={project.repoUrl} target="_blank" rel="noreferrer noopener" data-testid="overview-repo">{project.repoUrl}</a>
          {:else}
            <span class="mono muted" data-testid="overview-repo">not provisioned yet</span>
          {/if}
        </dd>
        <dt>Branch</dt>
        <dd><code class="mono" data-testid="overview-branch">{project.defaultBranch || '—'}</code></dd>
        <dt>Build session</dt>
        <dd><code class="mono" data-testid="overview-session">{sessionId || '—'}</code></dd>
      </dl>
    {/snippet}
  </Card>
</div>

<style>
  .overview {
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 20px);
    padding: var(--space-6, 24px);
    max-inline-size: 64rem;
  }
  .overview__head {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }
  .overview__title {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    flex-wrap: wrap;
  }
  .overview__name {
    margin: 0;
    /* the identity moment — the serif display voice for a page title (P-D4). */
    font-family: var(--font-display, var(--font-serif, serif));
    font-size: var(--font-size-headline, var(--font-size-title, 28px));
    font-weight: 600;
    color: var(--eden-app-fg, var(--color-on-surface));
  }
  .overview__idea {
    margin: 0;
    color: var(--eden-app-muted, var(--color-outline));
    font-size: var(--font-size-body-large, 15px);
    max-inline-size: 60ch;
  }
  .card__title {
    font-size: var(--font-size-body-large, 15px);
    color: var(--eden-app-fg, var(--color-on-surface));
  }
  .card__foot {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted, var(--color-outline));
  }
  .chips {
    list-style: none;
    margin: var(--space-3, 12px) 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2, 8px);
  }
  .coords {
    margin: 0;
    display: grid;
    grid-template-columns: minmax(7rem, max-content) 1fr;
    gap: var(--space-2, 8px) var(--space-4, 16px);
    align-items: baseline;
  }
  .coords dt {
    color: var(--eden-app-muted, var(--color-outline));
    font-size: var(--font-size-caption, 12px);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .coords dd {
    margin: 0;
    min-inline-size: 0;
    overflow-wrap: anywhere;
  }
  .mono {
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    color: var(--eden-app-fg, var(--color-on-surface));
  }
  .muted {
    color: var(--eden-app-muted, var(--color-outline));
  }
  .link {
    color: var(--color-primary);
    text-decoration: none;
  }
  .link:hover {
    text-decoration: underline;
  }
  .link:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
</style>
