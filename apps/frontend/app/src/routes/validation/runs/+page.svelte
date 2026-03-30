<script lang="ts">
  import { onMount } from 'svelte';
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
    Clock,
    Loader2,
    Search,
    Hand,
    Moon,
    GitBranch,
    GitCommit,
    Shield,
    Zap,
    FlaskConical,
    Flame,
    Play,
    AlertCircle,
    Radio,
    Cpu,
    Layers,
    RefreshCw,
    SkipForward,
    Ban,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ValidationRun, ValidationTrigger, ValidationStage, Product, Pagination } from '$lib/types/models';
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
    { value: 'ACTIVE', label: 'Active' },
    { value: 'PASSED', label: 'Passed' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  const STAGE_OPTIONS = [
    { value: 'smoke', label: 'Smoke' },
    { value: 'silicon', label: 'Silicon' },
    { value: 'integration', label: 'Integration' },
    { value: 'nightly', label: 'Nightly' },
    { value: 'fuota', label: 'FUOTA' },
  ];

  // Stage badge config (matches builds page pattern)
  const STAGE_BADGE: Record<string, { icon: typeof Zap; color: string }> = {
    smoke:       { icon: Flame,       color: 'text-text-secondary bg-surface-2' },
    silicon:     { icon: Cpu,         color: 'text-text-secondary bg-surface-2' },
    integration: { icon: FlaskConical, color: 'text-text-secondary bg-surface-2' },
    nightly:     { icon: Moon,        color: 'text-warning bg-warning-muted' },
    fuota:       { icon: Radio,       color: 'text-info bg-info-muted' },
  };

  const VARIANT_OPTIONS = [
    { value: 'debug', label: 'Debug' },
    { value: 'release', label: 'Release' },
    { value: 'mfg', label: 'Manufacturing' },
  ];

  // List state
  let runs = $state<ValidationRun[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let currentPage = $state(1);
  let refreshing = $state(false);

  // Filters (inline dropdowns, like builds page)
  let statusFilter = $state('');
  let stageFilter = $state('');
  let searchQuery = $state('');
  let productOptions = $state<{ value: string; label: string }[]>([]);
  let productFilter = $state('');

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

  // Smart filtering (client-side for search, server-side for status/stage)
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
    if (name.includes('nightly')) return 'nightly';
    if (name.includes('integration')) return 'integration';
    if (name.includes('smoke')) return 'smoke';
    if (name.includes('silicon')) return 'silicon';
    return 'fuota';
  }

  function getTriggerType(run: ValidationRun): string {
    const config = run.config as Record<string, unknown> | null;
    if (config?.bitbucketPrId || config?.pullRequestId) return 'bitbucket';
    if (config?.nightlyRun || config?.scheduled) return 'scheduled';
    if (config?.pipelineId) return 'ci';
    return 'manual';
  }

  function getTriggerLabel(run: ValidationRun): string {
    const config = run.config as Record<string, unknown> | null;
    const type = getTriggerType(run);
    if (type === 'bitbucket') {
      const prId = config?.bitbucketPrId || config?.pullRequestId || '';
      return prId ? `PR #${prId}` : 'Bitbucket PR';
    }
    if (type === 'ci') return 'Pipeline';
    if (type === 'scheduled') return 'Nightly';
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

  function getImageTag(run: ValidationRun): string | undefined {
    const config = run.config as Record<string, unknown> | null;
    return (config?.trigger as any)?.imageTag as string | undefined;
  }

  function getDuration(run: ValidationRun): string | null {
    if (!run.startedAt) return null;
    const start = new Date(run.startedAt).getTime();
    const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  function getFailedTests(run: ValidationRun): string[] {
    const executions = (run as any).executions as any[] | undefined;
    if (executions?.length) {
      return executions
        .filter(ex => ex.status === 'FAILED')
        .map(ex => ex.test?.name || 'Unknown test')
        .slice(0, 3);
    }
    return [];
  }

  function getCurrentTest(run: ValidationRun): string | null {
    const executions = (run as any).executions as any[] | undefined;
    if (executions?.length) {
      const running = executions.find(ex => ex.status === 'RUNNING');
      return running?.test?.name || null;
    }
    return null;
  }

  async function fetchRuns(): Promise<void> {
    try {
      const params = new URLSearchParams();
      params.set('page', String(currentPage));
      params.set('limit', '50');
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiFetch<ApiResponse<{ data: ValidationRun[]; pagination: Pagination }>>(
        '/v2/sessions?' + params.toString()
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
      const res = await api.post<ApiResponse<ValidationRun>>('/v2/sessions', body);
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
    const interval = setInterval(() => fetchRuns(), 10000);
    return () => clearInterval(interval);
  });

  $effect(() => { const _p = currentPage; fetchRuns(); });
  $effect(() => { const _s = statusFilter; const _st = stageFilter; currentPage = 1; });
</script>

<svelte:head>
  <title>Validation Runs — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Validation Runs"
      description="Hardware test results for firmware validation"
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

  <!-- Filter bar (matches builds page layout) -->
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <Select bind:value={statusFilter} placeholder="All statuses" options={STATUS_OPTIONS} />
    {#if productOptions.length > 0}
      <Select bind:value={productFilter} placeholder="All products" options={productOptions} />
    {/if}
    <Select bind:value={stageFilter} placeholder="All stages" options={STAGE_OPTIONS} />
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

  <!-- Runs list (compact, dense style matching builds page) -->
  {#if loading}
    <LoadingState message="Loading validation runs..." />
  {:else if filteredRuns.length === 0}
    <EmptyState message={searchQuery ? 'No runs match your search.' : 'No validation runs found.'} />
  {:else}
    <div class="space-y-2">
      {#each filteredRuns as run (run.id)}
        {@const stage = getStage(run)}
        {@const stageBadge = STAGE_BADGE[stage]}
        {@const config = run.config as Record<string, unknown> | null}
        {@const failedTests = getFailedTests(run)}
        {@const currentTest = getCurrentTest(run)}
        {@const serialNumber = getSerialNumber(run)}
        {@const fwVersion = getFirmwareVersion(run)}
        {@const imageTag = getImageTag(run)}
        {@const triggerType = getTriggerType(run)}
        {@const passed = run.passedCount ?? 0}
        {@const failed = run.failedCount ?? 0}
        {@const total = run.targetCount ?? 0}

        <button
          onclick={() => goto(`/validation/runs/${run.id}`)}
          class="w-full rounded-lg border border-border bg-surface-0 px-4 py-3 text-left transition-colors hover:bg-surface-1"
        >
          <!-- Row 1: Product + badges + status + duration + time -->
          <div class="flex items-center justify-between gap-4">
            <div class="flex items-center gap-2 min-w-0 flex-wrap">
              <Package size={16} class="flex-shrink-0 text-text-tertiary" />
              <span class="text-sm font-medium text-text-primary">
                {run.product?.name || 'Unknown'}
              </span>
              <!-- Stage badge -->
              {#if stageBadge}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs font-medium {stageBadge.color}">
                  {@const StageBadgeIcon = stageBadge.icon}
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
              <!-- Pipeline link (if triggered from a pipeline) -->
              {#if config?.pipelineId}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <span
                  role="link"
                  tabindex="0"
                  onclick={(e) => { e.stopPropagation(); goto(`/builds/pipelines/${config?.pipelineId}`); }}
                  class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-info-muted text-info text-2xs font-medium hover:bg-info/20 cursor-pointer transition-colors"
                  title="View build pipeline"
                >
                  <GitCommit size={10} />
                  Build
                </span>
              {/if}
              <!-- Trigger source (only non-pipeline sources) -->
              {#if triggerType === 'bitbucket'}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-info-muted text-info text-2xs font-medium">
                  <BitbucketIcon size={10} />
                  {getTriggerLabel(run)}
                </span>
              {:else if triggerType === 'scheduled'}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warning-muted text-warning text-2xs font-medium">
                  <Moon size={10} />
                  Nightly
                </span>
              {/if}
              <StatusBadge status={run.status} />
              {#if run.status === 'ACTIVE'}
                <Loader2 size={12} class="text-accent animate-spin" />
              {/if}
            </div>
            <div class="flex items-center gap-3 text-2xs text-text-tertiary flex-shrink-0">
              {#if getDuration(run)}
                <span class="tabular-nums">{getDuration(run)}</span>
              {/if}
              <span title={formatDateTime(run.createdAt)}>
                {formatTimeAgo(run.createdAt)}
              </span>
            </div>
          </div>

          <!-- Row 2: Test counts + progress + failed tests / current test -->
          <div class="flex items-center gap-3 mt-2 text-2xs flex-wrap">
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

            <!-- Progress bar (inline, compact) -->
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
            {:else if run.createdBy}
              <span class="ml-auto text-text-tertiary">
                {run.createdBy.name}
              </span>
            {/if}
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
