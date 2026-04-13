<script lang="ts">
  import { onMount } from 'svelte';
  import { GitBranch, Hammer, ListTodo, FlaskConical, AlertCircle } from 'lucide-svelte';
  import { fetchBuildRuns } from '$lib/services/ci';
  import { getQueueStats } from '$lib/services/queue';
  import { apiFetch } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { ValidationRun, Pagination } from '$lib/types/models';

  interface Props {
    productId: string;
    productName: string;
  }

  let { productId, productName }: Props = $props();

  let loading = $state(true);
  let error = $state<string | null>(null);

  let buildRunCount = $state(0);
  let activeBuildRuns = $state(0);
  let buildCount = $state(0);
  let queueCount = $state(0);
  let runCount = $state(0);
  let activeRuns = $state(0);

  const cards = $derived([
    { label: 'Build Runs', value: buildRunCount, active: activeBuildRuns, activeLabel: 'running', icon: GitBranch },
    { label: 'Builds', value: buildCount, active: 0, activeLabel: '', icon: Hammer },
    { label: 'Queue', value: queueCount, active: 0, activeLabel: '', icon: ListTodo },
    { label: 'Runs', value: runCount, active: activeRuns, activeLabel: 'active', icon: FlaskConical },
  ]);

  async function loadMetrics() {
    loading = true;
    error = null;
    try {
      const [buildRunsRes, queueRes, runsRes] = await Promise.all([
        fetchBuildRuns({ product: productName, limit: 50 }),
        getQueueStats().catch(() => ({ total: 0, byStatus: { QUEUED: 0 }, avgWaitSeconds: null })),
        apiFetch<ApiResponse<{ data: ValidationRun[]; pagination: Pagination }>>(
          '/v2/runs?type=VALIDATION&limit=50'
        ).catch(() => ({ data: { data: [] as ValidationRun[], pagination: { total: 0, page: 1, limit: 50, pages: 0 } } })),
      ]);

      const allBuildRuns = buildRunsRes.data;
      buildRunCount = buildRunsRes.pagination.total || allBuildRuns.length;
      activeBuildRuns = allBuildRuns.filter(p => p.status === 'BUILDING' || p.status === 'VALIDATING').length;
      buildCount = allBuildRuns.reduce((sum, p) => sum + (p.completedBuilds ?? 0), 0);
      queueCount = (queueRes as any).byStatus?.QUEUED ?? (queueRes as any).total ?? 0;

      const runs = runsRes.data.data || [];
      const productRuns = runs.filter(r => r.productId === productId);
      runCount = productRuns.length;
      activeRuns = productRuns.filter(r => r.status === 'ACTIVE').length;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load metrics';
    } finally {
      loading = false;
    }
  }

  onMount(() => { loadMetrics(); });
</script>

{#if error}
  <div class="flex items-center gap-2 rounded-lg border border-error bg-surface-1 p-3 text-sm text-error">
    <AlertCircle size={16} />
    {error}
  </div>
{/if}

<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
  {#each cards as card}
    <div class="rounded-lg border border-border bg-surface-1 p-4">
      {#if loading}
        <div class="space-y-3">
          <div class="h-4 w-20 animate-pulse rounded bg-surface-2"></div>
          <div class="h-8 w-16 animate-pulse rounded bg-surface-2"></div>
          <div class="h-3 w-24 animate-pulse rounded bg-surface-2"></div>
        </div>
      {:else}
        {@const CardIcon = card.icon}
        <div class="flex items-center gap-2 text-(--color-text-tertiary)">
          <CardIcon size={14} />
          <span class="text-xs font-medium">{card.label}</span>
        </div>
        <p class="mt-2 text-2xl font-semibold text-(--color-text-primary)">{card.value}</p>
        {#if card.active > 0}
          <p class="mt-1 text-xs text-accent">{card.active} {card.activeLabel}</p>
        {:else}
          <p class="mt-1 text-xs text-(--color-text-tertiary)">none active</p>
        {/if}
      {/if}
    </div>
  {/each}
</div>
