<script lang="ts">
  import { onMount } from 'svelte';
  import {
    CircuitBoard, FlaskConical, Factory, Hammer, Cpu,
    GitBranch, ExternalLink, Layers,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import type { Product } from '$lib/types/models';
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
  const enabledStages = $derived(stageConfigs.filter((s: any) => s.enabled));

  // Map revision IDs to version names for stage display
  const revisionMap = $derived(
    Object.fromEntries(revisions.map((r) => [r.id, r.version]))
  );

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
        api.get(`/v2/sessions?productId=${product.id}&limit=5&type=VALIDATION`),
        api.get(`/v2/sessions?productId=${product.id}&limit=1&type=MANUFACTURING`),
      ]);
      if (buildsRes.status === 'fulfilled' && buildsRes.value.ok) {
        const d = await buildsRes.value.json();
        recentBuilds = d.data?.data || [];
        totalBuilds = d.data?.pagination?.total ?? 0;
      }
      if (runsRes.status === 'fulfilled' && runsRes.value.ok) {
        const d = await runsRes.value.json();
        recentRuns = d.data?.data || [];
        totalRuns = d.data?.pagination?.total ?? 0;
      }
      if (mfgRes.status === 'fulfilled' && mfgRes.value.ok) {
        const d = await mfgRes.value.json();
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
<div class="grid grid-cols-2 gap-3 sm:grid-cols-5 mb-6">
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

  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Cpu size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Targets</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{product.targets?.length ?? 0}</div>
    <div class="text-2xs text-text-tertiary">{(product.targets?.length ?? 0) === 0 ? 'no targets' : 'SoC targets'}</div>
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
  <!-- Left: Validation stages -->
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-text-primary">Validation Stages</h3>
      {#if stageConfigs.length > 0}
        <span class="text-2xs text-text-tertiary">{enabledStages.length} of {stageConfigs.length} enabled</span>
      {/if}
    </div>
    {#if stageConfigs.length === 0}
      <div class="rounded-lg border border-dashed border-border bg-surface-0 p-6 text-center">
        <FlaskConical size={24} class="mx-auto mb-2 text-text-tertiary opacity-30" />
        <p class="text-sm text-text-secondary">No validation stages configured</p>
        <p class="text-2xs text-text-tertiary mt-1">Go to the Validation tab to set up test stages for this product.</p>
      </div>
    {:else}
      <div class="rounded-lg border border-border overflow-hidden">
        {#each stageConfigs as cfg}
          <div class="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
            <div class="w-6 h-6 flex items-center justify-center rounded text-[10px] font-bold {cfg.enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
              {cfg.stage}
            </div>
            <span class="text-sm font-medium text-text-primary">{cfg.name}</span>
            {#if cfg.boardRevisionId && revisionMap[cfg.boardRevisionId]}
              <span class="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-accent-muted text-accent">{revisionMap[cfg.boardRevisionId]}</span>
            {/if}
            {#if cfg.buildMatrix?.length}
              <span class="flex items-center gap-1 text-2xs text-text-tertiary" title="{cfg.buildMatrix.length} build matrix entries">
                <Layers size={10} />
                {cfg.buildMatrix.length}
              </span>
            {/if}
            <div class="flex-1"></div>
            <StatusBadge status={cfg.enabled ? 'ACTIVE' : 'DISABLED'} />
            {#if cfg.triggerTypes?.length > 0}
              <div class="flex gap-1">
                {#each cfg.triggerTypes as trigger}
                  <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-2 text-text-tertiary">{trigger}</span>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
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
                <TimeDisplay date={run.createdAt} />
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>
