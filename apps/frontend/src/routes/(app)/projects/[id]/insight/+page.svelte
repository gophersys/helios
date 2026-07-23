<script lang="ts">
  // /projects/[id]/insight — the project spine's INSIGHT view (doc 17 §5). Fetches the codeinsight
  // Report over the project's worktree (GatewayClient.insight → GET /projects/{id}/insight) and renders
  // @eden/visualization's HotspotMap (churn × complexity scatter) plus the Report summary numbers
  // (files / functions / maintainability via StatRow). It DEGRADES HONESTLY (P-D6): a 404/503 fault or an
  // empty report (e.g. no analyzable Go in the worktree yet) renders an explanatory EmptyState — never a
  // spinner-forever, never a fake chart. Token-driven via @eden/theme; the spine tab nav pins above.
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenLightTheme, edenDarkTheme } from '$lib/theme/edenTheme';
  import { themePreference } from '$lib/theme/themePreference.svelte';
  import { Button, Card, StatRow, Spinner, EmptyState, type Stat } from '@eden/primitives';
  import { HotspotMap, type Report } from '@eden/visualization';
  import ProjectSpineNav from '$lib/dashboard/ProjectSpineNav.svelte';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = $derived(themePreference.resolvedMode === 'dark' ? edenDarkTheme : edenLightTheme);
  const projectId = $derived(page.params.id ?? '');

  type Phase = 'loading' | 'ready' | 'empty' | 'error';
  let phase = $state<Phase>('loading');
  let report = $state<Report | null>(null);
  // The honest-degrade reason (a typed Kind when the gateway spoke, or a fallback string).
  let reason = $state<{ kind: string; message: string } | null>(null);

  // The summary numbers the StatRow surfaces — files (entity count), lines, and the maintainability
  // rating (A–E). Only real Report.summary fields; no fabricated metrics.
  const summaryStats = $derived.by<Stat[]>(() => {
    if (!report) return [];
    const s = report.summary;
    return [
      { label: 'files', value: String(s.entityCount) },
      { label: 'lines', value: String(s.lines) },
      { label: 'maintainability', value: s.maintainabilityRating || '—' },
    ];
  });

  async function load(): Promise<void> {
    const id = projectId;
    phase = 'loading';
    report = null;
    reason = null;
    if (!id) {
      phase = 'error';
      reason = { kind: 'invalid', message: 'No project id in the route.' };
      return;
    }
    try {
      const next = await client.insight(id);
      if (id !== projectId) return;
      // An empty report (no analyzable entities) is a HONEST degrade, not an error — the worktree has
      // nothing the analyzer can chart yet (e.g. no Go source committed). Render the explanatory
      // EmptyState, never a blank chart.
      if (!next.entities || next.entities.length === 0) {
        report = next;
        phase = 'empty';
        return;
      }
      report = next;
      phase = 'ready';
    } catch (cause) {
      if (id !== projectId) return;
      phase = 'error';
      reason =
        cause instanceof GatewayError
          ? { kind: cause.kind, message: cause.message }
          : { kind: 'unknown', message: cause instanceof Error ? cause.message : String(cause) };
    }
  }

  // Re-fetch whenever the route id changes (a client-side nav between two projects).
  $effect(() => {
    void projectId;
    void load();
  });

  /** A human line for the degrade reason (honest, per fault Kind). */
  function degradeBody(): string {
    if (phase === 'empty') {
      return 'Eden analyzed this project but found nothing to chart yet — there is no analyzable source in the worktree. Once the build writes code, the hotspot map fills in.';
    }
    const kind = reason?.kind ?? 'unknown';
    if (kind === 'not-found')
      return 'This project has no insight report — it may not exist, or its worktree is not on this node.';
    if (kind === 'unavailable')
      return 'The insight report is not available yet: the project has no materialized worktree, or the analysis exceeded its time budget. Try again once the build has run.';
    return reason?.message ?? 'The insight report could not be loaded.';
  }
</script>

<svelte:head><title>Eden — Insight</title></svelte:head>

<div class="spine-page">
  <ProjectSpineNav {projectId} />

  <div class="insight" data-testid="project-insight">
    {#if phase === 'loading'}
      <div class="insight__loading" data-testid="insight-loading">
        <Spinner variant="accent" label="Analyzing the repository" {theme} />
        <p class="insight__loading-line">Analyzing the repository…</p>
      </div>
    {:else if phase === 'ready' && report}
      {@const rep = report}
      <!-- The summary numbers (files / lines / maintainability) + the churn × complexity hotspot map. -->
      <Card variant="raised" {theme} aria-label="Insight summary">
        {#snippet header()}
          <strong class="card__title">Codebase insight</strong>
        {/snippet}
        {#snippet body()}
          <StatRow stats={summaryStats} {theme} />
        {/snippet}
        {#snippet footer()}
          <span class="card__foot" data-testid="insight-commit"
            >{rep.repository.identifier} · {rep.repository.headCommit.slice(0, 8)}</span
          >
        {/snippet}
      </Card>

      <div class="insight__map" data-testid="insight-hotspot">
        <HotspotMap entities={rep.entities} title="Hotspot map: churn versus complexity" {theme} />
      </div>
    {:else}
      <!-- HONEST DEGRADE (P-D6): an empty report OR a 404/503 fault renders an explanatory EmptyState,
           never a spinner-forever or a fake chart. -->
      <div class="insight__empty" data-testid="insight-empty">
        <EmptyState
          {theme}
          headline={phase === 'empty' ? 'Nothing to chart yet' : 'No insight available'}
          body={degradeBody()}
        >
          {#snippet action()}
            <Button
              variant="primary"
              {theme}
              onclick={() => goto(`/projects/${encodeURIComponent(projectId)}`)}
            >
              Back to overview
            </Button>
          {/snippet}
        </EmptyState>
      </div>
    {/if}
  </div>
</div>

<style>
  .spine-page {
    display: flex;
    flex-direction: column;
    min-block-size: 100%;
  }
  .insight {
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 20px);
    padding: var(--space-6, 24px);
    max-inline-size: 72rem;
  }
  .insight__loading {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: 12vh var(--space-6, 24px);
    justify-content: center;
  }
  .insight__loading-line {
    margin: 0;
    color: var(--muted-foreground, var(--color-outline));
    font-size: var(--font-size-label, 13px);
  }
  .card__title {
    font-size: var(--font-size-body-large, 15px);
    color: var(--foreground, var(--color-on-surface));
  }
  .card__foot {
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-caption, 12px);
    color: var(--muted-foreground, var(--color-outline));
  }
  .insight__map {
    overflow: auto;
  }
  .insight__empty {
    margin-block-start: 6vh;
  }
</style>
