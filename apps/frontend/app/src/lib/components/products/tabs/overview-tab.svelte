<script lang="ts">
  import { onMount } from 'svelte';
  import {
    CircuitBoard, Cpu, Hammer, FlaskConical, Factory, Package,
    Clock, CheckCircle, XCircle, AlertTriangle, ArrowRight,
    Activity, Zap,
  } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import type { Product } from '$lib/types/models';
  import { api } from '$lib/api';

  interface Props {
    product: Product;
    canManage: boolean;
  }

  let { product, canManage }: Props = $props();

  const revisions = $derived(
    (product.boards || []).flatMap((b) => b.revisions || [])
  );
  const activeRevisions = $derived(revisions.filter((r) => r.status === 'ACTIVE'));
  const stageConfigs = $derived((product as any).stageConfigs || []);
  const enabledStages = $derived(stageConfigs.filter((s: any) => s.enabled));

  // Recent activity
  let recentBuilds = $state<any[]>([]);
  let recentRuns = $state<any[]>([]);
  let loadingActivity = $state(true);

  onMount(async () => {
    try {
      const [buildsRes, runsRes] = await Promise.allSettled([
        api.get(`/v2/builds?productId=${product.id}&limit=5`),
        api.get(`/v2/sessions?productId=${product.id}&limit=5`),
      ]);
      if (buildsRes.status === 'fulfilled' && buildsRes.value.ok) {
        const d = await buildsRes.value.json();
        recentBuilds = d.data?.data || [];
      }
      if (runsRes.status === 'fulfilled' && runsRes.value.ok) {
        const d = await runsRes.value.json();
        recentRuns = d.data?.data || [];
      }
    } catch {
      // Non-critical — overview still shows static data
    } finally {
      loadingActivity = false;
    }
  });
</script>

<!-- Stats row -->
<div class="grid grid-cols-2 gap-3 sm:grid-cols-5 mb-6">
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <CircuitBoard size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Hardware</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{activeRevisions.length}</div>
    <div class="text-2xs text-text-tertiary">{revisions.length} total revisions</div>
  </div>
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <FlaskConical size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Validation</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{enabledStages.length}<span class="text-sm text-text-tertiary">/{stageConfigs.length}</span></div>
    <div class="text-2xs text-text-tertiary">stages enabled</div>
  </div>
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Factory size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Manufacturing</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">—</div>
    <div class="text-2xs text-text-tertiary">not configured</div>
  </div>
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Hammer size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Builds</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{recentBuilds.length > 0 ? recentBuilds.length : '—'}</div>
    <div class="text-2xs text-text-tertiary">{recentBuilds.length > 0 ? 'recent' : 'no recent builds'}</div>
  </div>
  <div class="rounded-lg border border-border bg-surface-0 p-3">
    <div class="flex items-center gap-2 text-text-tertiary mb-1">
      <Cpu size={14} />
      <span class="text-2xs font-medium uppercase tracking-wider">Targets</span>
    </div>
    <div class="text-xl font-semibold text-text-primary">{product.targets?.length ?? 0}</div>
    <div class="text-2xs text-text-tertiary">SoC targets</div>
  </div>
</div>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
  <!-- Left column -->
  <div class="space-y-6">
    <!-- Validation stages -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-text-primary">Validation Stages</h3>
        <span class="text-2xs text-text-tertiary">{enabledStages.length} of {stageConfigs.length} enabled</span>
      </div>
      {#if stageConfigs.length === 0}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <FlaskConical size={20} class="mx-auto mb-2 text-text-tertiary opacity-40" />
          <p class="text-sm text-text-tertiary">No validation stages configured yet.</p>
        </div>
      {:else}
        <div class="rounded-lg border border-border overflow-hidden">
          {#each stageConfigs as cfg}
            <div class="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
              <div class="w-6 h-6 flex items-center justify-center rounded text-[10px] font-bold {cfg.enabled ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
                {cfg.stage}
              </div>
              <span class="text-sm font-medium text-text-primary flex-1">{cfg.name}</span>
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

    <!-- Manufacturing -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-text-primary">Manufacturing</h3>
      </div>
      <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
        <Factory size={20} class="mx-auto mb-2 text-text-tertiary opacity-40" />
        <p class="text-sm text-text-tertiary">Manufacturing not configured for this product.</p>
        <p class="text-2xs text-text-tertiary mt-1">Set up POST sequences and production test flows in the Manufacturing tab.</p>
      </div>
    </div>
  </div>

  <!-- Right column -->
  <div class="space-y-6">
    <!-- Recent builds -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-text-primary">Recent Builds</h3>
      </div>
      {#if loadingActivity}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
        </div>
      {:else if recentBuilds.length === 0}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <Hammer size={20} class="mx-auto mb-2 text-text-tertiary opacity-40" />
          <p class="text-sm text-text-tertiary">No builds yet.</p>
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
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-text-primary">Recent Validation Runs</h3>
      </div>
      {#if loadingActivity}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent mx-auto"></div>
        </div>
      {:else if recentRuns.length === 0}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <FlaskConical size={20} class="mx-auto mb-2 text-text-tertiary opacity-40" />
          <p class="text-sm text-text-tertiary">No validation runs yet.</p>
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

    <!-- Hardware summary -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-text-primary">Hardware</h3>
      </div>
      {#if revisions.length === 0}
        <div class="rounded-lg border border-border bg-surface-0 p-4 text-center">
          <CircuitBoard size={20} class="mx-auto mb-2 text-text-tertiary opacity-40" />
          <p class="text-sm text-text-tertiary">No hardware revisions configured.</p>
        </div>
      {:else}
        <div class="rounded-lg border border-border overflow-hidden">
          {#each revisions as rev}
            <div class="flex items-center gap-3 px-4 py-2.5 border-b border-border-subtle last:border-b-0">
              <CircuitBoard size={14} class="text-accent shrink-0" />
              <span class="text-sm font-semibold text-text-primary">{rev.version}</span>
              <StatusBadge status={rev.status} />
              <span class="font-mono text-2xs text-text-tertiary flex-1">{rev.ckBoardsName}</span>
              {#if rev.targets?.length > 0}
                <div class="flex gap-2">
                  {#each rev.targets as target}
                    <span class="font-mono text-2xs text-text-secondary">{target.soc}</span>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>
