<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowLeft } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { ValidationRun, ValidationExecution } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatDuration } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  const auth = getAuth();

  const runIdA = $derived($page.url.searchParams.get('a') ?? '');
  const runIdB = $derived($page.url.searchParams.get('b') ?? '');

  let runA = $state<ValidationRun | null>(null);
  let runB = $state<ValidationRun | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  interface TestComparison {
    testName: string;
    category: string;
    statusA: string | null;
    statusB: string | null;
    durationA: number | null;
    durationB: number | null;
    powerA: number | null;
    powerB: number | null;
    differs: boolean;
  }

  const comparisons = $derived.by((): TestComparison[] => {
    if (!runA || !runB) return [];

    const execsA = runA.executions ?? [];
    const execsB = runB.executions ?? [];

    const mapA = new Map<string, ValidationExecution>();
    const mapB = new Map<string, ValidationExecution>();

    for (const ex of execsA) mapA.set(ex.test?.name ?? ex.testId, ex);
    for (const ex of execsB) mapB.set(ex.test?.name ?? ex.testId, ex);

    const allNames = new Set([...mapA.keys(), ...mapB.keys()]);
    const rows: TestComparison[] = [];

    for (const name of allNames) {
      const a = mapA.get(name);
      const b = mapB.get(name);

      const statusA = a?.status ?? null;
      const statusB = b?.status ?? null;

      const durationA = getDuration(a);
      const durationB = getDuration(b);

      const powerA = getPower(a);
      const powerB = getPower(b);

      rows.push({
        testName: name,
        category: a?.test?.category ?? b?.test?.category ?? '—',
        statusA,
        statusB,
        durationA,
        durationB,
        powerA,
        powerB,
        differs: statusA !== statusB && statusA !== null && statusB !== null,
      });
    }

    return rows.sort((a, b) => a.testName.localeCompare(b.testName));
  });

  const maxPower = $derived.by(() => {
    let max = 0;
    for (const c of comparisons) {
      if (c.powerA !== null && c.powerA > max) max = c.powerA;
      if (c.powerB !== null && c.powerB > max) max = c.powerB;
    }
    return max || 1;
  });

  const hasPowerData = $derived(comparisons.some(c => c.powerA !== null || c.powerB !== null));

  function getDuration(ex: ValidationExecution | undefined): number | null {
    if (!ex?.results?.length) return null;
    for (const r of ex.results) {
      if (r.result && typeof r.result === 'object' && 'durationS' in r.result) {
        return (r.result as Record<string, unknown>).durationS as number;
      }
    }
    return null;
  }

  function getPower(ex: ValidationExecution | undefined): number | null {
    if (!ex?.results?.length) return null;
    for (const r of ex.results) {
      if (r.result && typeof r.result === 'object' && 'measurements' in r.result) {
        const m = (r.result as Record<string, unknown>).measurements as Record<string, unknown> | undefined;
        if (m && 'currentMa' in m) return m.currentMa as number;
      }
    }
    return null;
  }

  function durationMs(run: ValidationRun | null): number | null {
    if (!run?.startedAt) return null;
    const start = new Date(run.startedAt).getTime();
    const end = run.completedAt ? new Date(run.completedAt).getTime() : Date.now();
    return end - start;
  }

  function rowClass(c: TestComparison): string {
    if (!c.differs) return '';
    const isPassed = (s: string | null) => s === 'PASSED';
    if (isPassed(c.statusA) && !isPassed(c.statusB)) return 'bg-error-muted/30';
    if (!isPassed(c.statusA) && isPassed(c.statusB)) return 'bg-success-muted/30';
    return 'bg-warning-muted/30';
  }

  async function fetchRuns(): Promise<void> {
    if (!runIdA || !runIdB) {
      error = 'Both run IDs (a and b) are required as query parameters.';
      loading = false;
      return;
    }

    try {
      const [resA, resB] = await Promise.all([
        apiFetch<ApiResponse<ValidationRun>>(`/v2/runs/${runIdA}`),
        apiFetch<ApiResponse<ValidationRun>>(`/v2/runs/${runIdB}`),
      ]);
      runA = resA.data;
      runB = resB.data;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load runs';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) {
      goto('/');
      return;
    }
    fetchRuns();
  });
</script>

<svelte:head>
  <title>Compare Runs — Validation — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <button
    onclick={() => goto('/validation/runs')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    Validation Runs
  </button>

  {#if loading}
    <LoadingState message="Loading runs for comparison..." />
  {:else if error}
    <ErrorAlert message={error} />
  {:else if runA && runB}
    <h1 class="text-lg font-semibold text-text-primary mb-1">Run Comparison</h1>
    <p class="text-xs text-text-tertiary mb-6">
      {runA.name} vs {runB.name}
    </p>

    <!-- Summary cards -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <!-- Run A -->
      <div class="card">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-2xs font-medium uppercase tracking-wider text-accent">Run A</span>
          <StatusBadge status={runA.status} />
        </div>
        <h2 class="text-sm font-medium text-text-primary truncate">{runA.name}</h2>
        <div class="mt-3 grid grid-cols-3 gap-3 text-center">
          <div>
            <div class="text-xl font-semibold tabular-nums text-text-primary">{runA.passedCount}</div>
            <div class="text-2xs text-success">Passed</div>
          </div>
          <div>
            <div class="text-xl font-semibold tabular-nums text-text-primary">{runA.failedCount}</div>
            <div class="text-2xs text-error">Failed</div>
          </div>
          <div>
            <div class="text-xl font-semibold tabular-nums text-text-primary">
              {durationMs(runA) !== null ? formatDuration(durationMs(runA)!) : '—'}
            </div>
            <div class="text-2xs text-text-tertiary">Duration</div>
          </div>
        </div>
      </div>

      <!-- Run B -->
      <div class="card">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-2xs font-medium uppercase tracking-wider text-info">Run B</span>
          <StatusBadge status={runB.status} />
        </div>
        <h2 class="text-sm font-medium text-text-primary truncate">{runB.name}</h2>
        <div class="mt-3 grid grid-cols-3 gap-3 text-center">
          <div>
            <div class="text-xl font-semibold tabular-nums text-text-primary">{runB.passedCount}</div>
            <div class="text-2xs text-success">Passed</div>
          </div>
          <div>
            <div class="text-xl font-semibold tabular-nums text-text-primary">{runB.failedCount}</div>
            <div class="text-2xs text-error">Failed</div>
          </div>
          <div>
            <div class="text-xl font-semibold tabular-nums text-text-primary">
              {durationMs(runB) !== null ? formatDuration(durationMs(runB)!) : '—'}
            </div>
            <div class="text-2xs text-text-tertiary">Duration</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Test comparison table -->
    <h2 class="mb-3 text-sm font-medium text-text-primary">
      Test Results
      <span class="text-text-tertiary font-normal">
        ({comparisons.length} tests, {comparisons.filter(c => c.differs).length} differ)
      </span>
    </h2>

    {#if comparisons.length === 0}
      <div class="card card-sm text-center text-sm text-text-tertiary">
        No test executions to compare.
      </div>
    {:else}
      <div class="table-wrapper mb-6">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              <th class="table-header">Test</th>
              <th class="table-header">Category</th>
              <th class="table-header text-center">Run A</th>
              <th class="table-header text-right">A Duration</th>
              <th class="table-header text-center">Run B</th>
              <th class="table-header text-right">B Duration</th>
            </tr>
          </thead>
          <tbody>
            {#each comparisons as comp (comp.testName)}
              <tr class="table-row {rowClass(comp)}">
                <td class="table-cell font-medium text-text-primary text-xs">{comp.testName}</td>
                <td class="table-cell text-text-secondary text-xs">{comp.category}</td>
                <td class="table-cell text-center">
                  {#if comp.statusA}
                    <StatusBadge status={comp.statusA} />
                  {:else}
                    <span class="text-text-tertiary text-xs">—</span>
                  {/if}
                </td>
                <td class="table-cell text-right tabular-nums text-text-secondary text-xs">
                  {comp.durationA !== null ? `${comp.durationA.toFixed(2)}s` : '—'}
                </td>
                <td class="table-cell text-center">
                  {#if comp.statusB}
                    <StatusBadge status={comp.statusB} />
                  {:else}
                    <span class="text-text-tertiary text-xs">—</span>
                  {/if}
                </td>
                <td class="table-cell text-right tabular-nums text-text-secondary text-xs">
                  {comp.durationB !== null ? `${comp.durationB.toFixed(2)}s` : '—'}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <!-- Power measurement comparison -->
    {#if hasPowerData}
      <h2 class="mb-3 text-sm font-medium text-text-primary">
        Power Measurements
        <span class="text-text-tertiary font-normal">(mA)</span>
      </h2>

      <div class="space-y-2 mb-6">
        {#each comparisons.filter(c => c.powerA !== null || c.powerB !== null) as comp (comp.testName)}
          <div class="card card-sm">
            <div class="text-xs font-medium text-text-primary mb-2">{comp.testName}</div>
            <div class="space-y-1.5">
              <!-- Run A bar -->
              <div class="flex items-center gap-2">
                <span class="text-2xs text-accent w-8 shrink-0">A</span>
                <div class="flex-1 h-4 bg-surface-2 rounded-sm overflow-hidden">
                  {#if comp.powerA !== null}
                    <div
                      class="h-full bg-accent/60 rounded-sm transition-all"
                      style:width="{(comp.powerA / maxPower) * 100}%"
                    ></div>
                  {/if}
                </div>
                <span class="text-2xs tabular-nums text-text-secondary w-16 text-right">
                  {comp.powerA !== null ? `${comp.powerA.toFixed(1)} mA` : '—'}
                </span>
              </div>
              <!-- Run B bar -->
              <div class="flex items-center gap-2">
                <span class="text-2xs text-info w-8 shrink-0">B</span>
                <div class="flex-1 h-4 bg-surface-2 rounded-sm overflow-hidden">
                  {#if comp.powerB !== null}
                    <div
                      class="h-full bg-info/60 rounded-sm transition-all"
                      style:width="{(comp.powerB / maxPower) * 100}%"
                    ></div>
                  {/if}
                </div>
                <span class="text-2xs tabular-nums text-text-secondary w-16 text-right">
                  {comp.powerB !== null ? `${comp.powerB.toFixed(1)} mA` : '—'}
                </span>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
