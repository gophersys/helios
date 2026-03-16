<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    Calendar,
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Clock,
    Cpu,
    FlaskConical,
    GitBranch,
    GitCommit,
    Grid3X3,
    Hammer,
    Layers,
    Moon,
    Package,
    Plus,
    Radio,
    RefreshCw,
    User,
    Webhook,
    Zap,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildJob, Pipeline, MatrixLabel, ValidationStage } from '$lib/types/ci';
  import { MATRIX_LABEL_DISPLAY, STAGE_DISPLAY } from '$lib/types/ci';
  import type { Pagination } from '$lib/types/models';
  import { fetchPipelines, fetchBuilds, triggerPipeline } from '$lib/services/ci';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('builds:manage'));

  const STATUS_OPTIONS = [
    { value: 'BUILDING', label: 'Building' },
    { value: 'SUCCESS', label: 'Success' },
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

  // Per-stage icon and color config for list badges
  const STAGE_BADGE: Record<string, { icon: typeof Zap; color: string }> = {
    smoke:       { icon: Zap,    color: 'text-text-secondary bg-surface-2' },
    silicon:     { icon: Cpu,    color: 'text-text-secondary bg-surface-2' },
    integration: { icon: Layers, color: 'text-text-secondary bg-surface-2' },
    nightly:     { icon: Moon,   color: 'text-warning bg-warning-muted' },
    fuota:       { icon: Radio,  color: 'text-info bg-info-muted' },
  };

  // Trigger source display config
  const TRIGGER_CONFIG: Record<string, { icon: typeof Webhook; label: string; color: string }> = {
    webhook: { icon: GitCommit, label: 'Bitbucket', color: 'text-info bg-info-muted' },
    manual: { icon: User, label: 'Manual', color: 'text-accent bg-accent-muted' },
    scheduled: { icon: Calendar, label: 'Scheduled', color: 'text-warning bg-warning-muted' },
  };

  function getTriggerConfig(type: string) {
    return TRIGGER_CONFIG[type] || TRIGGER_CONFIG.manual;
  }

  // Product info mapping (board -> display name, repo slug, hardware rev)
  const PRODUCT_INFO: Record<string, { name: string; repo: string; rev: string }> = {
    alpha_b0: { name: 'Alpha', repo: 'alpha_fw', rev: 'B0' },
    sigma5_b0: { name: 'Sigma5', repo: 'sigma5_fw', rev: 'B0' },
    sigma5_c0: { name: 'Sigma5', repo: 'sigma5_fw', rev: 'C0' },
    theta_c0: { name: 'Theta', repo: 'theta_fw', rev: 'C0' },
  };

  function getProductInfo(product: string): { name: string; repo: string; rev: string } {
    const key = product.toLowerCase().replace(/\s+/g, '_');
    return PRODUCT_INFO[key] ?? { name: product, repo: `${key}_fw`, rev: '' };
  }

  // Get build matrix summary for validation pipelines
  function getMatrixSummary(pipeline: Pipeline): string | null {
    if (!pipeline.builds || pipeline.builds.length === 0) return null;
    if (!pipeline.matrixMode) return null;

    const statusCounts = new Map<string, number>();
    for (const build of pipeline.builds) {
      const status = build.status;
      statusCounts.set(status, (statusCounts.get(status) || 0) + 1);
    }

    const parts: string[] = [];
    const order = ['SUCCESS', 'BUILDING', 'FAILED', 'QUEUED', 'CANCELLED'];
    for (const status of order) {
      const count = statusCounts.get(status);
      if (count && count > 0) {
        parts.push(`${count} ${status.toLowerCase()}`);
      }
    }
    return parts.join(', ');
  }

  // Get unique variants from builds
  function getVariantSummary(pipeline: Pipeline): string {
    if (!pipeline.builds || pipeline.builds.length === 0) return '';
    const variants = new Set(pipeline.builds.map(b => b.variant));
    return Array.from(variants).join(', ');
  }

  type ViewMode = 'pipelines' | 'jobs';
  let viewMode = $state<ViewMode>('jobs');

  let pipelines = $state<Pipeline[]>([]);
  let buildJobs = $state<BuildJob[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let statusFilter = $state('');
  let productFilter = $state('');
  let branchFilter = $state('');
  let stageFilter = $state('');
  let currentPage = $state(1);
  let refreshing = $state(false);
  let productOptions = $state<{ value: string; label: string }[]>([]);

  // Trigger form
  let showForm = $state(false);
  let formProduct = $state('');
  let formBoard = $state('');
  let formTarget = $state('');
  let formVariant = $state('');
  let formBranch = $state('');
  let formNodeId = $state('');
  let formSerialNumber = $state('');
  let formValidate = $state(false);
  let submitting = $state(false);

  async function loadPipelines(): Promise<void> {
    try {
      const res = await fetchPipelines({
        page: currentPage,
        limit: 25,
        status: statusFilter || undefined,
        product: productFilter || undefined,
        branch: branchFilter || undefined,
        matrixMode: stageFilter || undefined,
      });
      pipelines = res.data;
      pagination = res.pagination;
      error = null;

      // Extract unique products for filter dropdown (only on first load)
      if (productOptions.length === 0 && res.data.length > 0) {
        const products = new Set<string>();
        res.data.forEach(p => { if (p.product) products.add(p.product); });
        productOptions = Array.from(products).sort().map(p => ({ value: p, label: p }));
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load pipelines';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function loadBuildJobs(): Promise<void> {
    try {
      const res = await fetchBuilds({
        page: currentPage,
        limit: 25,
        status: statusFilter || undefined,
      });
      buildJobs = res.data;
      pagination = res.pagination;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load build jobs';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function loadData(): void {
    if (viewMode === 'pipelines') loadPipelines();
    else loadBuildJobs();
  }

  function refresh(): void {
    refreshing = true;
    loadData();
  }

  function resetForm(): void {
    formProduct = '';
    formBoard = '';
    formTarget = '';
    formVariant = '';
    formBranch = '';
    formNodeId = '';
    formSerialNumber = '';
    formValidate = false;
    showForm = false;
  }

  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;
    try {
      const pipeline = await triggerPipeline({
        product: formProduct,
        board: formBoard,
        target: formTarget,
        variant: formVariant,
        branch: formBranch,
        validate: formValidate,
        nodeId: formNodeId || undefined,
        serialNumber: formSerialNumber || undefined,
      });
      resetForm();
      goto(`/builds/pipelines/${pipeline.id}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to trigger pipeline';
    } finally {
      submitting = false;
    }
  }

  function pipelineDuration(pipeline: Pipeline): string {
    // For list view, calculate from startedAt/finishedAt or use build durations
    if (pipeline.startedAt && pipeline.finishedAt) {
      const duration = new Date(pipeline.finishedAt).getTime() - new Date(pipeline.startedAt).getTime();
      return formatDuration(duration);
    }
    if (pipeline.builds && pipeline.builds.length > 0) {
      const totalSeconds = pipeline.builds.reduce((sum, b) => sum + (b.durationSeconds ?? 0), 0);
      if (totalSeconds > 0) return formatDuration(totalSeconds * 1000);
    }
    return '--';
  }

  onMount(() => {
    if (!auth.hasPermission('builds:view')) {
      goto('/');
      return;
    }
    loadData();

    // Auto-refresh every 10s
    const interval = setInterval(() => {
      loadData();
    }, 10000);
    return () => clearInterval(interval);
  });

  $effect(() => {
    const _p = currentPage;
    loadData();
  });

  $effect(() => {
    const _s = statusFilter;
    const _p = productFilter;
    const _b = branchFilter;
    const _st = stageFilter;
    currentPage = 1;
  });
</script>

<svelte:head>
  <title>Builds - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Builds"
      description="Firmware build pipelines - build, flash, and validate in one flow."
    />
  </div>

  <ErrorAlert message={error} />

  {#if showForm}
    <FormCard title="Trigger Pipeline" onClose={resetForm}>
      <form onsubmit={handleSubmit} class="space-y-3">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput bind:value={formProduct} label="Product" placeholder="e.g. alpha" required />
          <TextInput bind:value={formBoard} label="Board" placeholder="e.g. alpha_b0" required />
        </div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput bind:value={formTarget} label="Target" placeholder="e.g. nrf52840" required />
          <Select
            bind:value={formVariant}
            label="Variant"
            placeholder="Select variant"
            options={[
              { value: 'debug', label: 'Debug' },
              { value: 'release', label: 'Release' },
              { value: 'mfg', label: 'Manufacturing' },
            ]}
            required
          />
        </div>
        <TextInput bind:value={formBranch} label="Branch" placeholder="e.g. main" required />

        <div class="flex items-center gap-2 pt-1">
          <input
            type="checkbox"
            id="validate-toggle"
            bind:checked={formValidate}
            class="rounded border-border"
          />
          <label for="validate-toggle" class="text-sm text-text-secondary">
            Run validation after build + flash
          </label>
        </div>

        {#if formValidate}
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextInput bind:value={formNodeId} label="MTIB Node ID" placeholder="Node for flashing" />
            <TextInput bind:value={formSerialNumber} label="Serial Number" placeholder="DUT serial" />
          </div>
        {/if}

        <div class="flex justify-end gap-2 pt-1">
          <button type="button" onclick={resetForm} class="btn btn-sm">Cancel</button>
          <button type="submit" disabled={submitting} class="btn btn-sm btn-primary">
            {submitting ? 'Triggering...' : 'Trigger Pipeline'}
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  <div class="mb-4 flex flex-wrap items-center gap-3">
    <Select
      bind:value={statusFilter}
      placeholder="All statuses"
      options={STATUS_OPTIONS}
    />
    {#if productOptions.length > 0}
      <Select
        bind:value={productFilter}
        placeholder="All products"
        options={productOptions}
      />
    {/if}
    <Select
      bind:value={stageFilter}
      placeholder="All stages"
      options={STAGE_OPTIONS}
    />
    <TextInput
      bind:value={branchFilter}
      placeholder="Filter by branch..."
    />
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} builds
    </span>
    <button
      onclick={refresh}
      disabled={refreshing}
      class="btn btn-sm flex items-center gap-1.5"
      title="Refresh"
    >
      <RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
    </button>
    {#if canManage}
      <button
        onclick={() => { showForm = true; }}
        class="btn btn-sm btn-primary flex items-center gap-1.5"
      >
        <Plus size={14} />
        Trigger Build
      </button>
    {/if}
  </div>

  <!-- View toggle -->
  <div class="mb-4 flex gap-1 border-b border-border">
    <button
      onclick={() => { viewMode = 'jobs'; loading = true; loadData(); }}
      class="px-4 py-2 text-sm font-medium transition-colors {viewMode === 'jobs' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      Build Jobs
    </button>
    <button
      onclick={() => { viewMode = 'pipelines'; loading = true; loadData(); }}
      class="px-4 py-2 text-sm font-medium transition-colors {viewMode === 'pipelines' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      Pipelines
    </button>
  </div>

  {#if loading}
    <LoadingState message="Loading {viewMode === 'pipelines' ? 'pipelines' : 'build jobs'}..." />
  {:else if viewMode === 'jobs'}
    {#if buildJobs.length === 0}
      <EmptyState message="No build jobs found." />
    {:else}
      <div class="space-y-2">
        {#each buildJobs as build (build.id)}
          <button
            onclick={() => goto(`/builds/${build.status === 'CACHED' && build.reusedFromId ? build.reusedFromId : build.id}`)}
            class="w-full rounded-lg border border-border bg-surface-0 px-4 py-3 text-left transition-colors hover:bg-surface-1"
          >
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center gap-3 min-w-0">
                <Hammer size={16} class="flex-shrink-0 text-text-tertiary" />
                <span class="text-sm font-medium text-text-primary">
                  {build.product || 'Unknown'}
                </span>
                <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary font-mono">
                  {build.variant}
                </span>
                {#if build.board}
                  <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary">
                    {build.board}
                  </span>
                {/if}
                {#if build.branch}
                  <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
                    <GitBranch size={10} />
                    {build.branch}
                  </span>
                {/if}
                {#if build.commitSha}
                  <span class="inline-flex items-center gap-1 rounded bg-info-muted px-1.5 py-0.5 text-2xs text-info font-mono font-medium">
                    <GitCommit size={10} />
                    {build.commitSha.slice(0, 7)}
                  </span>
                {/if}
                {#if build.versionString}
                  <span class="inline-flex items-center rounded bg-accent-muted px-1.5 py-0.5 text-2xs text-accent font-mono font-medium">
                    v{build.versionString}
                  </span>
                {/if}
                <StatusBadge status={build.status} />
              </div>
              <div class="flex items-center gap-3 text-2xs text-text-tertiary flex-shrink-0">
                {#if build.durationSeconds}
                  <span class="tabular-nums">{formatDuration(build.durationSeconds * 1000)}</span>
                {/if}
                <span title={formatDateTime(build.createdAt)}>
                  {formatTimeAgo(build.createdAt)}
                </span>
              </div>
            </div>
            {#if build.configFlags?.versionOverride}
              <div class="mt-1.5 text-2xs text-text-tertiary">
                Version override: <span class="font-mono text-text-secondary">{build.configFlags.versionOverride}</span>
              </div>
            {/if}
            {#if build.artifacts && build.artifacts.length > 0}
              <div class="mt-1.5 flex items-center gap-2 text-2xs text-text-tertiary">
                <span>{build.artifacts.length} artifact{build.artifacts.length !== 1 ? 's' : ''}</span>
                {#each build.artifacts.slice(0, 4) as art}
                  <span class="font-mono bg-surface-2 px-1 py-0.5 rounded">{art.name}</span>
                {/each}
                {#if build.artifacts.length > 4}
                  <span>+{build.artifacts.length - 4} more</span>
                {/if}
              </div>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  {:else if pipelines.length === 0}
    <EmptyState message="No pipelines found." />
  {:else}
    <div class="space-y-2">
      {#each pipelines as pipeline (pipeline.id)}
        {@const trigger = getTriggerConfig(pipeline.triggerType)}
        {@const productInfo = getProductInfo(pipeline.product ?? '')}
        <button
          onclick={() => goto(`/builds/pipelines/${pipeline.id}`)}
          class="w-full rounded-lg border border-border bg-surface-0 px-4 py-3 text-left transition-colors hover:bg-surface-1"
        >
          <div class="flex items-center justify-between gap-4 mb-2">
            <div class="flex items-center gap-3 min-w-0">
              <Package size={16} class="flex-shrink-0 text-text-tertiary" />
              <span class="text-sm font-medium text-text-primary truncate">
                {productInfo.name}
              </span>
              {#if productInfo.rev}
                <span class="inline-flex items-center gap-1 rounded bg-info-muted px-1.5 py-0.5 text-2xs text-info font-medium">
                  {productInfo.rev}
                </span>
              {/if}
              {#if pipeline.branch}
                <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
                  <GitBranch size={10} />
                  {pipeline.branch}
                </span>
              {/if}
              {#if pipeline.commitSha}
                <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono text-text-tertiary">
                  <GitCommit size={10} />
                  {pipeline.commitSha.slice(0, 7)}
                </span>
              {/if}
              <StatusBadge status={pipeline.status} />
            </div>
            <div class="flex items-center gap-3 text-2xs text-text-tertiary flex-shrink-0">
              <span class="tabular-nums">{pipelineDuration(pipeline)}</span>
              <span title={formatDateTime(pipeline.createdAt)}>
                {formatTimeAgo(pipeline.createdAt)}
              </span>
            </div>
          </div>
          <!-- Build info row with trigger source -->
          <div class="flex items-center gap-3 text-2xs flex-wrap">
            <span class="text-text-tertiary">
              {pipeline.completedBuilds ?? 0}/{pipeline.expectedBuilds ?? 0} builds
            </span>
            <!-- Trigger source badge -->
            <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded {trigger.color} font-medium">
              <svelte:component this={trigger.icon} size={10} />
              {trigger.label}
            </span>
            <!-- Stage indicator -->
            {#if pipeline.matrixMode && STAGE_BADGE[pipeline.matrixMode]}
              {@const badge = STAGE_BADGE[pipeline.matrixMode]}
              {@const stage = STAGE_DISPLAY[pipeline.matrixMode as ValidationStage]}
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded {badge.color} font-medium" title={stage?.description ?? pipeline.matrixMode}>
                <svelte:component this={badge.icon} size={10} />
                {stage?.name ?? pipeline.matrixMode}
              </span>
            {/if}
            <!-- Validation indicator -->
            {#if pipeline.validationRunId}
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-success-muted text-success font-medium" title="Validation run linked">
                <FlaskConical size={10} />
                Validated
              </span>
            {:else if pipeline.autoValidate}
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-muted text-accent font-medium" title="Will auto-trigger validation">
                <FlaskConical size={10} />
                Auto
              </span>
            {/if}
            <!-- Build summary -->
            {#if pipeline.builds && pipeline.builds.length > 0}
              {@const summary = getMatrixSummary(pipeline)}
              {#if summary}
                <span class="text-text-tertiary">{summary}</span>
              {:else}
                <span class="text-text-tertiary">
                  {getVariantSummary(pipeline)}
                </span>
              {/if}
            {/if}
            <!-- Show build versions with status colors and duration -->
            {#if pipeline.builds && pipeline.builds.length > 0}
              <div class="flex items-center gap-1.5 ml-auto">
                {#each pipeline.builds.slice(0, 6) as build}
                  <span
                    class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs font-mono {
                      build.status === 'SUCCESS' ? 'bg-success-muted text-success' :
                      build.status === 'FAILED' ? 'bg-error-muted text-error' :
                      build.status === 'BUILDING' ? 'bg-warning-muted text-warning animate-pulse' :
                      build.status === 'BLOCKED' ? 'bg-surface-2 text-text-tertiary' :
                      'bg-surface-2 text-text-tertiary'
                    }"
                    title="{build.variant ?? ''} {build.versionString ?? ''} - {build.status}{build.durationSeconds ? ` (${formatDuration(build.durationSeconds * 1000)})` : ''}"
                  >
                    {build.versionString ?? '...'}
                  </span>
                {/each}
                {#if pipeline.builds.length > 6}
                  <span class="text-2xs text-text-tertiary">+{pipeline.builds.length - 6}</span>
                {/if}
              </div>
            {/if}
          </div>
        </button>
      {/each}
    </div>
  {/if}

  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages}
      </span>
      <div class="flex items-center gap-1">
        <button
          onclick={() => (currentPage = 1)}
          disabled={currentPage <= 1}
          aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.min(pagination.pages, currentPage + 1))}
          disabled={currentPage >= pagination.pages}
          aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (currentPage = pagination.pages)}
          disabled={currentPage >= pagination.pages}
          aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>
