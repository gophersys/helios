<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronRight,
    ChevronLeft,
    ChevronsLeft,
    ChevronsRight,
    Plus,
    Package,
    CheckCircle2,
    XCircle,
    Loader2,
    Search,
    Moon,
    GitCommit,
    Zap,
    FlaskConical,
    Flame,
    Play,
    Radio,
    Cpu,
    RefreshCw,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ValidationRun, ValidationStage, Product, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import { BitbucketIcon } from '$lib/components/icons';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('validation:manage'));

  const STATUS_OPTIONS = [
    { value: 'ACTIVE', label: 'Running' },
    { value: 'PASSED', label: 'Passed' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  const STAGE_OPTIONS = [
    { value: 'smoke', label: 'Smoke' },
    { value: 'driver', label: 'Driver' },
    { value: 'integration', label: 'Integration' },
    { value: 'regression', label: 'Regression' },
    { value: 'fuota', label: 'FUOTA' },
  ];

  const STAGE_BADGE: Record<string, { icon: typeof Zap; color: string }> = {
    smoke:       { icon: Flame,        color: 'text-text-secondary bg-surface-2' },
    driver:      { icon: Cpu,          color: 'text-text-secondary bg-surface-2' },
    integration: { icon: FlaskConical, color: 'text-text-secondary bg-surface-2' },
    regression:  { icon: Moon,         color: 'text-warning bg-warning-muted' },
    fuota:       { icon: Radio,        color: 'text-info bg-info-muted' },
  };

  const DATE_RANGE_OPTIONS = [
    { value: '', label: 'All time' },
    { value: 'today', label: 'Today' },
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
  ];

  const VARIANT_OPTIONS = [
    { value: 'debug', label: 'Debug' },
    { value: 'release', label: 'Release' },
    { value: 'mfg', label: 'Manufacturing' },
  ];

  // List state
  let runs = $state<ValidationRun[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let currentPage = $state(1);
  let refreshing = $state(false);

  // Filters
  let statusFilter = $state('');
  let stageFilter = $state('');
  let productFilter = $state('');
  let dateRange = $state('');
  let searchQuery = $state('');
  let productOptions = $state<{ value: string; label: string }[]>([]);

  // Active status pills
  let activeStatuses = $state<Set<string>>(new Set());

  function toggleStatus(status: string) {
    const next = new Set(activeStatuses);
    if (next.has(status)) {
      next.delete(status);
    } else {
      next.add(status);
    }
    activeStatuses = next;
    currentPage = 1;
  }

  // Create form state
  let showForm = $state(false);
  let formName = $state('');
  let formProductId = $state('');
  let formNodeId = $state('');
  let formSerialNumber = $state('');
  let formVariant = $state('');
  let formStage = $state('fuota');
  let formNotes = $state('');
  let submitting = $state(false);
  let products = $state<{ value: string; label: string }[]>([]);
  let nodes = $state<{ value: string; label: string }[]>([]);

  // Auto-refresh
  let refreshInterval: ReturnType<typeof setInterval> | null = null;
  const hasActiveRuns = $derived(runs.some(r => r.status === 'ACTIVE'));

  // Smart filtering (client-side for search/stage/product, server-side for status)
  const filteredRuns = $derived.by(() => {
    let result = runs;

    // Client-side search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(r =>
        r.name.toLowerCase().includes(q) ||
        r.product?.name?.toLowerCase().includes(q) ||
        (r.config as any)?.serialNumber?.toLowerCase().includes(q) ||
        (r.config as any)?.firmwareVersion?.toLowerCase().includes(q) ||
        r.createdBy?.name?.toLowerCase().includes(q)
      );
    }

    // Client-side product filter
    if (productFilter) {
      result = result.filter(r => r.product?.name === productFilter);
    }

    // Client-side stage filter
    if (stageFilter) {
      result = result.filter(r => getStage(r) === stageFilter);
    }

    // Status pills filter
    if (activeStatuses.size > 0) {
      result = result.filter(r => {
        const effectiveStatus = getEffectiveStatus(r);
        return activeStatuses.has(effectiveStatus);
      });
    }

    // Smart sorting: active first, then by recency
    return result.toSorted((a, b) => {
      if (a.status === 'ACTIVE' && b.status !== 'ACTIVE') return -1;
      if (b.status === 'ACTIVE' && a.status !== 'ACTIVE') return 1;
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });
  });

  // Helpers
  function getStage(run: ValidationRun): string {
    if (run.stage) return run.stage;
    const config = run.config as Record<string, unknown> | null;
    if (config?.stage) return config.stage as string;
    const name = run.name.toLowerCase();
    if (name.includes('fuota')) return 'fuota';
    if (name.includes('regression')) return 'regression';
    if (name.includes('integration')) return 'integration';
    if (name.includes('smoke')) return 'smoke';
    if (name.includes('driver')) return 'driver';
    return 'fuota';
  }

  function getEffectiveStatus(run: ValidationRun): string {
    if (run.status === 'ACTIVE') return 'RUNNING';
    if (run.status === 'COMPLETED') {
      return run.failedCount > 0 ? 'FAILED' : 'PASSED';
    }
    return run.status;
  }

  function getTriggerType(run: ValidationRun): string {
    const config = run.config as Record<string, unknown> | null;
    if (config?.bitbucketPrId || config?.pullRequestId) return 'bitbucket';
    if (config?.regressionRun || config?.nightlyRun || config?.scheduled) return 'scheduled';
    if (config?.runId) return 'ci';
    return 'manual';
  }

  function getTriggerLabel(run: ValidationRun): string {
    const config = run.config as Record<string, unknown> | null;
    const type = getTriggerType(run);
    if (type === 'bitbucket') {
      const prId = config?.bitbucketPrId || config?.pullRequestId || '';
      return prId ? `PR #${prId}` : 'Bitbucket PR';
    }
    if (type === 'ci') return 'Build Run';
    if (type === 'scheduled') return 'Scheduled';
    return run.createdBy?.name || 'Manual';
  }

  function getSerialNumber(run: ValidationRun): string | undefined {
    const config = run.config as Record<string, unknown> | null;
    return (config?.slot as any)?.dutSnr ?? config?.serialNumber as string | undefined;
  }

  function getFirmwareVersion(run: ValidationRun): string | undefined {
    const config = run.config as Record<string, unknown> | null;
    return config?.firmwareVersion as string | undefined ?? config?.firmwareVariant as string | undefined;
  }

  function getFixtureName(run: ValidationRun): string | undefined {
    const config = run.config as Record<string, unknown> | null;
    return (config?.slot as any)?.benchName ?? config?.benchName as string | undefined;
  }

  function getDuration(run: ValidationRun): string | null {
    if (!run.startedAt) return null;
    const start = new Date(run.startedAt).getTime();
    const end = run.completedAt ? new Date(run.completedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  function getFailedTests(run: ValidationRun): string[] {
    const executions = (run as any).executions as any[] | undefined;
    if (executions?.length) {
      return executions
        .filter((ex: any) => ex.status === 'FAILED')
        .map((ex: any) => ex.test?.name || 'Unknown test')
        .slice(0, 3);
    }
    return [];
  }

  function getCurrentTest(run: ValidationRun): string | null {
    const executions = (run as any).executions as any[] | undefined;
    if (executions?.length) {
      const running = executions.find((ex: any) => ex.status === 'RUNNING');
      return running?.test?.name || null;
    }
    return null;
  }

  function getStatusCounts(run: ValidationRun): { passed: number; failed: number; total: number } {
    return {
      passed: run.passedCount ?? 0,
      failed: run.failedCount ?? 0,
      total: run.targetCount ?? 0,
    };
  }

  async function fetchRuns(): Promise<void> {
    try {
      const params = new URLSearchParams();
      params.set('page', String(currentPage));
      params.set('limit', '25');
      if (statusFilter) params.set('status', statusFilter);

      // Date range filter
      if (dateRange) {
        const now = new Date();
        let from: Date | null = null;
        if (dateRange === 'today') {
          from = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        } else if (dateRange === '7d') {
          from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        } else if (dateRange === '30d') {
          from = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        }
        if (from) params.set('from', from.toISOString());
      }

      const res = await apiFetch<ApiResponse<{ data: ValidationRun[]; pagination: Pagination }>>(
        '/v2/runs?type=VALIDATION&' + params.toString()
      );

      runs = res.data.data;
      pagination = res.data.pagination;

      // Extract unique products for filter dropdown
      if (productOptions.length === 0 && runs.length > 0) {
        const prods = new Set<string>();
        runs.forEach(r => { if (r.product?.name) prods.add(r.product.name); });
        productOptions = Array.from(prods).sort().map(p => ({ value: p, label: p }));
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load validation runs';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function refresh(): void {
    refreshing = true;
    fetchRuns();
  }

  async function fetchDropdowns(): Promise<void> {
    try {
      const [prodRes, nodeRes] = await Promise.all([
        apiFetch<ApiResponse<{ data: Product[] }>>('/v2/products'),
        apiFetch<ApiResponse<{ data: { id: string; name: string }[] }>>('/v2/devices/mtibs'),
      ]);
      const prodList = Array.isArray(prodRes.data) ? prodRes.data : prodRes.data.data || [];
      products = prodList.map(p => ({ value: p.id, label: p.name }));
      const nodeList = Array.isArray(nodeRes.data) ? nodeRes.data : nodeRes.data.data || [];
      nodes = nodeList.map(n => ({ value: n.id, label: n.name }));
    } catch { /* fail silently */ }
  }

  function resetForm(): void {
    formName = ''; formProductId = ''; formNodeId = ''; formSerialNumber = '';
    formVariant = ''; formStage = 'fuota'; formNotes = ''; showForm = false;
  }

  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;
    const body: Record<string, unknown> = {
      name: formName, productId: formProductId, nodeId: formNodeId, serialNumber: formSerialNumber,
    };
    if (formVariant) body.firmwareVariant = formVariant;
    if (formStage) body.stage = formStage;
    if (formNotes.trim()) body.notes = formNotes.trim();
    try {
      const res = await api.post<ApiResponse<ValidationRun>>('/v2/runs', body);
      resetForm();
      await fetchRuns();
      if (res.data?.id) goto(`/validation/runs/${res.data.id}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create run';
    } finally {
      submitting = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) { goto('/'); return; }
    fetchRuns();
    refreshInterval = setInterval(() => fetchRuns(), 10000);
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
  });

  $effect(() => { const _p = currentPage; fetchRuns(); });
  $effect(() => {
    const _s = statusFilter;
    const _st = stageFilter;
    const _d = dateRange;
    currentPage = 1;
  });
</script>

<svelte:head>
  <title>Validation - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Validation"
      description="Hardware-in-the-loop test runs across all products and stages."
    />
  </div>

  <ErrorAlert message={error} />

  {#if showForm}
    <FormCard title="New Validation Run" onClose={resetForm}>
      <form onsubmit={handleSubmit} class="space-y-3">
        <TextInput bind:value={formName} label="Name" placeholder="e.g. Alpha Gate v0.5.1 PR-123" required />
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Select bind:value={formProductId} label="Product" placeholder="Select product" options={products} required />
          <Select bind:value={formNodeId} label="MTIB Node" placeholder="Select node" options={nodes} required />
        </div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <TextInput bind:value={formSerialNumber} label="Serial Number" placeholder="70B3D584C01E1FCC" required />
          <Select bind:value={formVariant} label="Firmware Variant" placeholder="Any variant" options={VARIANT_OPTIONS} />
          <Select bind:value={formStage} label="Test Stage" options={STAGE_OPTIONS} />
        </div>
        <div>
          <label for="notes" class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
          <textarea id="notes" bind:value={formNotes} rows={2} placeholder="Optional notes..."
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          ></textarea>
        </div>
        <div class="flex justify-end gap-2 pt-1">
          <button type="button" onclick={resetForm} class="btn btn-sm">Cancel</button>
          <button type="submit" disabled={submitting} class="btn btn-sm btn-primary">
            {submitting ? 'Creating...' : 'Create Run'}
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  <!-- Filter bar -->
  <div class="mb-4 flex flex-wrap items-center gap-3">
    {#if productOptions.length > 0}
      <Select bind:value={productFilter} placeholder="All products" options={productOptions} />
    {/if}
    <Select bind:value={stageFilter} placeholder="All stages" options={STAGE_OPTIONS} />
    <Select bind:value={dateRange} placeholder="All time" options={DATE_RANGE_OPTIONS} />

    <!-- Status pills -->
    <div class="flex items-center gap-1.5">
      {#each ['PASSED', 'FAILED', 'RUNNING', 'QUEUED', 'SKIPPED'] as status}
        <button
          onclick={() => toggleStatus(status)}
          class="rounded-full px-2.5 py-1 text-2xs font-medium transition-colors {activeStatuses.has(status)
            ? status === 'PASSED' ? 'bg-success text-white'
            : status === 'FAILED' ? 'bg-error text-white'
            : status === 'RUNNING' ? 'bg-accent text-white'
            : 'bg-surface-2 text-text-primary'
            : 'bg-surface-1 text-text-tertiary hover:bg-surface-2 hover:text-text-secondary'}"
        >
          {status}
        </button>
      {/each}
    </div>

    <div class="relative">
      <Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search..."
        class="pl-9 pr-3 py-1.5 w-48 text-sm rounded-lg border border-border bg-surface-0 text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
      />
    </div>
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} runs
    </span>
    <button onclick={refresh} disabled={refreshing} class="btn btn-sm flex items-center gap-1.5" title="Refresh">
      <RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
    </button>
    {#if canManage}
      <button onclick={() => { showForm = true; fetchDropdowns(); }} class="btn btn-sm btn-primary flex items-center gap-1.5">
        <Plus size={14} />
        New Run
      </button>
    {/if}
  </div>

  <!-- Runs list -->
  {#if loading}
    <LoadingState message="Loading validation runs..." />
  {:else if filteredRuns.length === 0}
    <EmptyState message={searchQuery || activeStatuses.size > 0 ? 'No runs match your filters.' : 'No validation runs found.'} />
  {:else}
    <div class="divide-y divide-border-subtle rounded-lg border border-border bg-surface-0">
      {#each filteredRuns as run (run.id)}
        {@const stage = getStage(run)}
        {@const stageBadge = STAGE_BADGE[stage]}
        {@const config = run.config as Record<string, unknown> | null}
        {@const failedTests = getFailedTests(run)}
        {@const currentTest = getCurrentTest(run)}
        {@const serialNumber = getSerialNumber(run)}
        {@const fwVersion = getFirmwareVersion(run)}
        {@const fixtureName = getFixtureName(run)}
        {@const triggerType = getTriggerType(run)}
        {@const { passed, failed, total } = getStatusCounts(run)}

        <button
          onclick={() => goto(`/validation/runs/${run.id}`)}
          class="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-surface-2/50"
        >
          <!-- Left: Run info -->
          <div class="min-w-0 flex-1">
            <!-- Row 1: Product + badges -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-medium text-text-primary">
                {run.product?.name || 'Unknown'}
              </span>
              <!-- Stage badge -->
              {#if stageBadge}
                {@const StageBadgeIcon = stageBadge.icon}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs font-medium {stageBadge.color}">
                  <StageBadgeIcon size={10} />
                  {stage.toUpperCase()}
                </span>
              {/if}
              <!-- Firmware version -->
              {#if fwVersion}
                <span class="inline-flex items-center rounded bg-accent-muted px-1.5 py-0.5 text-2xs text-accent font-mono font-medium">
                  {fwVersion}
                </span>
              {/if}
              <!-- Serial number -->
              {#if serialNumber}
                <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary font-mono">
                  {serialNumber}
                </span>
              {/if}
              <!-- Fixture name -->
              {#if fixtureName}
                <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
                  {fixtureName}
                </span>
              {/if}
              <!-- Trigger source -->
              {#if config?.runId}
                <span
                  role="link"
                  tabindex="0"
                  onclick={(e) => { e.stopPropagation(); goto(`/builds/runs/${config?.runId}`); }}
                  onkeydown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); goto(`/builds/runs/${config?.runId}`); }}}
                  class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-info-muted text-info text-2xs font-medium hover:bg-info/20 cursor-pointer transition-colors"
                  title="View build run"
                >
                  <GitCommit size={10} />
                  Build
                </span>
              {:else if triggerType === 'bitbucket'}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-info-muted text-info text-2xs font-medium">
                  <BitbucketIcon size={10} />
                  {getTriggerLabel(run)}
                </span>
              {:else if triggerType === 'scheduled'}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning text-2xs font-medium">
                  <Moon size={10} />
                  Scheduled
                </span>
              {:else}
                <span class="text-2xs text-text-tertiary">
                  {getTriggerLabel(run)}
                </span>
              {/if}
            </div>

            <!-- Row 2: Test counts + progress + failed tests / current test -->
            <div class="flex items-center gap-3 mt-1.5 text-2xs flex-wrap">
              <StatusBadge status={run.status} />
              {#if run.status === 'ACTIVE'}
                <Loader2 size={12} class="text-accent animate-spin" />
              {/if}
              <!-- Test counts -->
              <span class="flex items-center gap-1">
                <CheckCircle2 size={11} class="text-success" />
                <span class="text-text-primary font-medium">{passed}</span>
              </span>
              {#if failed > 0}
                <span class="flex items-center gap-1 text-error">
                  <XCircle size={11} />
                  <span class="font-medium">{failed}</span>
                </span>
              {/if}
              <span class="text-text-tertiary">/ {total} tests</span>

              <!-- Progress bar -->
              {#if total > 0}
                <div class="w-24 h-1.5 bg-surface-2 rounded-full overflow-hidden flex-shrink-0">
                  <div
                    class="h-full rounded-full transition-all duration-500 {failed > 0 ? 'bg-error' : run.status === 'ACTIVE' ? 'bg-accent' : 'bg-success'}"
                    style="width: {Math.round((passed + failed) / total * 100)}%"
                  ></div>
                </div>
              {/if}

              <!-- Failed tests or current test -->
              {#if failedTests.length > 0}
                <div class="flex items-center gap-1 ml-auto">
                  {#each failedTests as testName}
                    <span class="px-1.5 py-0.5 rounded bg-error/10 text-error font-mono">{testName}</span>
                  {/each}
                  {#if failed > 3}
                    <span class="text-error">+{failed - 3}</span>
                  {/if}
                </div>
              {:else if run.status === 'ACTIVE' && currentTest}
                <div class="flex items-center gap-1.5 ml-auto">
                  <Play size={10} class="text-accent" />
                  <span class="font-mono text-text-secondary">{currentTest}</span>
                </div>
              {/if}
            </div>
          </div>

          <!-- Right: Duration + time -->
          <div class="flex flex-col items-end gap-1 text-2xs text-text-tertiary flex-shrink-0">
            {#if getDuration(run)}
              <span class="tabular-nums">{getDuration(run)}</span>
            {/if}
            <span title={formatDateTime(run.createdAt)}>
              {formatTimeAgo(run.createdAt)}
            </span>
          </div>
        </button>
      {/each}
    </div>
  {/if}

  <!-- Pagination -->
  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages}
      </span>
      <div class="flex items-center gap-1">
        <button onclick={() => (currentPage = 1)} disabled={currentPage <= 1} aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30">
          <ChevronsLeft size={16} />
        </button>
        <button onclick={() => (currentPage = Math.max(1, currentPage - 1))} disabled={currentPage <= 1} aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30">
          <ChevronLeft size={16} />
        </button>
        <button onclick={() => (currentPage = Math.min(pagination.pages, currentPage + 1))} disabled={currentPage >= pagination.pages} aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30">
          <ChevronRight size={16} />
        </button>
        <button onclick={() => (currentPage = pagination.pages)} disabled={currentPage >= pagination.pages} aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30">
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>
