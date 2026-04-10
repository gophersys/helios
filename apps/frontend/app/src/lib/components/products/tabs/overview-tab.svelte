<script lang="ts">
  import { onMount } from 'svelte';
  import {
    CircuitBoard, FlaskConical, Factory, Hammer,
    GitBranch, ExternalLink, Layers,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import type { Product } from '$lib/types/models';
  import { STAGE_NAMES } from '$lib/types/stages';
  import { api } from '$lib/api';

  interface Props {
    product: Product;
    canManage: boolean;
  }

  let { product }: Props = $props();

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || [])
  );
  const activeRevisions = $derived(revisions.filter((r) => r.status === 'ACTIVE'));
  const stageConfigs = $derived((product as any).stageConfigs || []);
  const valStages = $derived(stageConfigs.filter((s: any) => s.stage <= 100));

  // Unique stage numbers (rows)
  const stageNumbers = $derived(
    ([...new Set(valStages.map((s: any) => s.stage))] as number[]).sort((a, b) => a - b)
  );

  // All revisions are columns — active revisions without stages show dashes
  const matrixRevisions = $derived(revisions);

  // Lookup: (stageNumber, revisionId) → config
  const stageMatrix = $derived(() => {
    const map = new Map<string, any>();
    for (const cfg of valStages) {
      if (cfg.boardRevisionId) {
        map.set(`${cfg.stage}:${cfg.boardRevisionId}`, cfg);
      }
    }
    return map;
  });

  function getStageCell(stage: number, revId: string): any | null {
    return stageMatrix().get(`${stage}:${revId}`) ?? null;
  }

  let recentBuilds = $state<any[]>([]);
  let recentRuns = $state<any[]>([]);
  let totalBuilds = $state(0);
  let totalRuns = $state(0);
  let totalMfgSessions = $state(0);
  let loading = $state(true);

  onMount(async () => {
    try {
      const [buildsRes, runsRes, mfgRes] = await Promise.allSettled([
        api.get(`/v2/builds?productId=${product.id}&limit=5`),
        api.get(`/v2/runs?productId=${product.id}&limit=5&type=VALIDATION`),
        api.get(`/v2/runs?productId=${product.id}&limit=1&type=MANUFACTURING`),
      ]);
      if (buildsRes.status === 'fulfilled') {
        const d = buildsRes.value as { data?: { data?: any[]; pagination?: { total?: number } } };
        recentBuilds = d.data?.data || [];
        totalBuilds = d.data?.pagination?.total ?? 0;
      }
      if (runsRes.status === 'fulfilled') {
        const d = runsRes.value as { data?: { data?: any[]; pagination?: { total?: number } } };
        recentRuns = d.data?.data || [];
        totalRuns = d.data?.pagination?.total ?? 0;
      }
      if (mfgRes.status === 'fulfilled') {
        const d = mfgRes.value as { data?: { pagination?: { total?: number } } };
        totalMfgSessions = d.data?.pagination?.total ?? 0;
      }
    } catch {
      // Non-critical
    } finally {
      loading = false;
    }
  });

  // Repo URLs from product metadata
  const fwRepoUrl = $derived(product.fwRepoSlug ? `https://bitbucket.org/corekinect/${product.fwRepoSlug}` : null);
  const mfgRepoUrl = $derived(product.mfgFwRepoSlug ? `https://bitbucket.org/corekinect/${product.mfgFwRepoSlug}` : null);
</script>

<!-- Stat cards -->
<div class="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-6">
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <CircuitBoard size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Hardware</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{activeRevisions.length}</div>
    <div class="text-2xs text-text-tertiary">{activeRevisions.length === 1 ? '1 active revision' : `${activeRevisions.length} active revisions`}</div>
  </div>

  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Hammer size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Builds</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{loading ? '—' : totalBuilds}</div>
    <div class="text-2xs text-text-tertiary">{totalBuilds === 0 ? 'no builds yet' : 'total builds'}</div>
  </div>

  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <FlaskConical size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Validation</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{loading ? '—' : totalRuns}</div>
    <div class="text-2xs text-text-tertiary">{totalRuns === 0 ? 'no runs yet' : 'total runs'}</div>
  </div>

  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Factory size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Manufacturing</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{loading ? '—' : totalMfgSessions}</div>
    <div class="text-2xs text-text-tertiary">{totalMfgSessions === 0 ? 'no sessions yet' : 'total sessions'}</div>
  </div>
</div>

<!-- Repos -->
{#if fwRepoUrl || mfgRepoUrl}
  <div class="mb-6">
    <h3 class="text-sm font-semibold text-text-primary mb-3">Repositories</h3>
    <div class="flex flex-wrap gap-3">
      {#if fwRepoUrl}
        <a href={fwRepoUrl} target="_blank" rel="noopener noreferrer"
          class="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-4 py-2.5 text-sm text-text-primary hover:border-accent hover:bg-surface-2 transition-colors">
          <GitBranch size={14} class="text-accent" />
          <span class="font-medium">{product.fwRepoSlug}</span>
          <span class="text-2xs text-text-tertiary">firmware</span>
          <ExternalLink size={12} class="text-text-tertiary" />
        </a>
      {/if}
      {#if mfgRepoUrl}
        <a href={mfgRepoUrl} target="_blank" rel="noopener noreferrer"
          class="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-4 py-2.5 text-sm text-text-primary hover:border-accent hover:bg-surface-2 transition-colors">
          <GitBranch size={14} class="text-warning" />
          <span class="font-medium">{product.mfgFwRepoSlug}</span>
          <span class="text-2xs text-text-tertiary">manufacturing</span>
          <ExternalLink size={12} class="text-text-tertiary" />
        </a>
      {/if}
    </div>
  </div>
{/if}

<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
  <!-- Left: Validation stage matrix -->
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-text-primary">Validation Stages</h3>
      {#if valStages.length > 0}
        {@const enabledCount = valStages.filter((s: any) => s.enabled).length}
        <span class="text-2xs text-text-tertiary">{enabledCount} of {valStages.length} enabled</span>
      {/if}
    </div>
    {#if valStages.length === 0}
      <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
        <FlaskConical size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
        <p class="text-sm text-text-secondary">No validation stages configured</p>
        <p class="text-2xs text-text-tertiary mt-1">Go to the Validation tab to set up test stages for this product.</p>
      </div>
    {:else}
      <!-- Stage × revision matrix table with sticky stage column -->
      <div class="rounded-lg border border-border overflow-x-auto">
        <table class="w-full text-sm border-collapse">
          <thead>
            <tr class="bg-surface-2">
              <th class="sticky left-0 z-10 bg-surface-2 text-left px-4 py-2 text-2xs font-semibold uppercase tracking-wider text-text-tertiary border-r border-border-subtle min-w-[140px]">Stage</th>
              {#each matrixRevisions as rev}
                <th class="text-center px-4 py-2 min-w-[120px]">
                  <span class="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded {rev.status === 'ACTIVE' ? 'bg-accent-muted text-accent' : 'bg-surface-1 text-text-tertiary'}">{rev.version}</span>
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each stageNumbers as stageNum}
              <tr class="border-t border-border-subtle">
                <td class="sticky left-0 z-10 bg-surface-0 px-4 py-2.5 border-r border-border-subtle">
                  <div class="flex items-center gap-2">
                    <div class="w-5 h-5 flex items-center justify-center rounded text-[10px] font-bold bg-accent text-white shrink-0">
                      {stageNum}
                    </div>
                    <span class="font-medium text-text-primary whitespace-nowrap">{STAGE_NAMES[stageNum] || `Stage ${stageNum}`}</span>
                  </div>
                </td>
                {#each matrixRevisions as rev}
                  {@const cell = getStageCell(stageNum, rev.id)}
                  <td class="text-center px-4 py-2.5">
                    {#if cell?.enabled && cell.triggerTypes?.length > 0}
                      <div class="flex flex-wrap justify-center gap-0.5">
                        {#each cell.triggerTypes as trigger}
                          <span class="text-[9px] font-mono px-1 py-0.5 rounded bg-accent-muted text-accent whitespace-nowrap">{trigger}</span>
                        {/each}
                      </div>
                    {:else}
                      <span class="text-text-tertiary opacity-30">—</span>
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>

  <!-- Right: Recent activity -->
  <div class="space-y-6">
    <!-- Recent builds -->
    <div>
      <h3 class="text-sm font-semibold text-text-primary mb-3">Recent Builds</h3>
      {#if loading}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
        </div>
      {:else if recentBuilds.length === 0}
        <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
          <Hammer size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
          <p class="text-sm text-text-secondary">No builds yet</p>
          <p class="text-2xs text-text-tertiary mt-1">Builds appear here when triggered by the CI pipeline or manually.</p>
        </div>
      {:else}
        <div class="rounded-lg border border-border overflow-hidden">
          {#each recentBuilds as build}
            <div class="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
              <StatusBadge status={build.status} />
              <span class="text-sm text-text-primary flex-1 truncate">{build.matrixLabel || build.variant}</span>
              <span class="font-mono text-2xs text-text-tertiary">v{build.versionString}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Recent validation runs -->
    <div>
      <h3 class="text-sm font-semibold text-text-primary mb-3">Recent Validation Runs</h3>
      {#if loading}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
        </div>
      {:else if recentRuns.length === 0}
        <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
          <FlaskConical size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
          <p class="text-sm text-text-secondary">No validation runs yet</p>
          <p class="text-2xs text-text-tertiary mt-1">Runs appear here when validation is triggered from the pipeline or manually.</p>
        </div>
      {:else}
        <div class="rounded-lg border border-border overflow-hidden">
          {#each recentRuns as run}
            <div class="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
              <StatusBadge status={run.status} />
              <span class="text-sm text-text-primary flex-1 truncate">{run.name}</span>
              {#if run.createdAt}
                <TimeDisplay datetime={run.createdAt} />
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>
