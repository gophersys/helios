<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    Activity,
    Check,
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Clock,
    Cpu,
    ExternalLink,
    FlaskConical,
    GitBranch,
    GitCommit,
    GitPullRequest,
    Grid3X3,
    Hammer,
    Layers,
    Loader2,
    Moon,
    Package,
    Plus,
    Radio,
    RefreshCw,
    Upload,
    X,
    Zap,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildJob, BuildArtifact, BuildRunDetail, BuildSummary, PrPipelineSummary, MatrixLabel, ValidationStage } from '$lib/types/ci';
  import { MATRIX_LABEL_DISPLAY, STAGE_DISPLAY } from '$lib/types/ci';
  import type { Pagination, Product } from '$lib/types/models';
  import { fetchBuildRuns, fetchBuilds, fetchBuildSummary, fetchPrPipelines, triggerBuildRun, createManualBuild, uploadBuildArtifact } from '$lib/services/ci';
  import { fetchProducts as fetchProductList } from '$lib/services/products';
  import { getTriggerConfig, getProductInfo } from '$lib/constants/builds';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('builds:manage'));

  // ── Stage config ──────────────────────────────────────────────
  const STAGE_ABBREV: Record<number, string> = { 1: 'SM', 2: 'SI', 3: 'IN', 4: 'NY', 5: 'FU' };
  const STAGE_NAMES: Record<number, string> = { 1: 'Smoke', 2: 'Silicon', 3: 'Integration', 4: 'Nightly', 5: 'FUOTA' };
  const ALL_STAGES = [1, 2, 3, 4, 5];

  // ── Filter options ────────────────────────────────────────────
  const STATUS_OPTIONS = [
    { value: 'PENDING', label: 'Pending' },
    { value: 'BUILDING', label: 'Building' },
    { value: 'SUCCESS', label: 'Success' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  const STAGE_OPTIONS = [
    { value: '1', label: 'Smoke' },
    { value: '2', label: 'Silicon' },
    { value: '3', label: 'Integration' },
    { value: '4', label: 'Nightly' },
    { value: '5', label: 'FUOTA' },
  ];

  const TRIGGER_TYPE_OPTIONS = [
    { value: 'pr_push', label: 'PR Push' },
    { value: 'pr_merge', label: 'PR Merge' },
    { value: 'manual', label: 'Manual' },
    { value: 'auto', label: 'Auto' },
    { value: 'schedule', label: 'Schedule' },
  ];

  const PR_STATUS_OPTIONS = [
    { value: 'active', label: 'Active' },
    { value: 'failed', label: 'Failed' },
    { value: 'completed', label: 'Completed' },
  ];

  // Trigger type badge config for build jobs
  const TRIGGER_TYPE_BADGE: Record<string, { color: string; label: string }> = {
    worker: { color: 'text-text-secondary bg-surface-2', label: 'Worker' },
    manual: { color: 'text-accent bg-accent-muted', label: 'Manual' },
    webhook: { color: 'text-info bg-info-muted', label: 'Webhook' },
    pr_push: { color: 'text-info bg-info-muted', label: 'PR Push' },
    pr_merge: { color: 'text-success bg-success-muted', label: 'PR Merge' },
    auto: { color: 'text-warning bg-warning-muted', label: 'Auto' },
    schedule: { color: 'text-text-secondary bg-surface-2', label: 'Schedule' },
  };

  // Per-stage icon and color config for list badges
  const STAGE_BADGE: Record<string, { icon: typeof Zap; color: string }> = {
    smoke:       { icon: Zap,    color: 'text-text-secondary bg-surface-2' },
    silicon:     { icon: Cpu,    color: 'text-text-secondary bg-surface-2' },
    integration: { icon: Layers, color: 'text-text-secondary bg-surface-2' },
    nightly:     { icon: Moon,   color: 'text-warning bg-warning-muted' },
    fuota:       { icon: Radio,  color: 'text-info bg-info-muted' },
  };

  const STAGE_TO_MATRIX_MODE: Record<string, string> = {
    '1': 'smoke',
    '2': 'silicon',
    '3': 'integration',
    '4': 'nightly',
    '5': 'fuota',
  };

  // ── View mode ─────────────────────────────────────────────────
  type ViewMode = 'prPipelines' | 'buildRuns' | 'jobs';
  let viewMode = $state<ViewMode>('prPipelines');

  // ── Shared state ──────────────────────────────────────────────
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let currentPage = $state(1);
  let refreshing = $state(false);
  let productOptions = $state<{ value: string; label: string }[]>([]);
  let products = $state<Product[]>([]);

  // ── Summary stats ─────────────────────────────────────────────
  let summary = $state<BuildSummary | null>(null);

  // ── PR Pipelines state ────────────────────────────────────────
  let prPipelines = $state<PrPipelineSummary[]>([]);
  let prProductFilter = $state('');
  let prStatusFilter = $state('');

  // ── Build Runs state ──────────────────────────────────────────
  let buildRuns = $state<BuildRunDetail[]>([]);
  let runsProductFilter = $state('');
  let runsStageFilter = $state('');
  let runsStatusFilter = $state('');
  let runsTriggerFilter = $state('');
  let runsBranchFilter = $state('');

  // ── Build Jobs state ──────────────────────────────────────────
  let buildJobs = $state<BuildJob[]>([]);
  let jobsStatusFilter = $state('');
  let jobsTriggerFilter = $state('');

  // ── Upload modal state ────────────────────────────────────────
  let showUploadModal = $state(false);
  let uploadStep = $state<'details' | 'artifacts'>('details');
  let uploadProducts = $state<Product[]>([]);
  let uploadProductId = $state('');
  let uploadBoard = $state('');
  let uploadTarget = $state('');
  let uploadVariant = $state('');
  let uploadVersion = $state('');
  let uploadBranch = $state('');
  let uploadNotes = $state('');
  let uploadSubmitting = $state(false);
  let uploadBuildId = $state<string | null>(null);
  let uploadingFile = $state(false);
  let uploadedArtifacts = $state<BuildArtifact[]>([]);
  let preselectedProductId = $state<string | null>(null);
  let artifactRole = $state('');
  let artifactProcessor = $state('');

  // ── Trigger form state ────────────────────────────────────────
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

  // ── Helper functions ──────────────────────────────────────────

  function getStageStatusClasses(status: string | null): string {
    if (!status) return 'bg-surface-2 text-text-tertiary';
    switch (status) {
      case 'SUCCESS':
      case 'COMPLETED':
        return 'bg-success-muted text-success';
      case 'BUILDING':
      case 'PENDING':
      case 'VALIDATING':
      case 'RUNNING':
        return 'bg-warning-muted text-warning';
      case 'FAILED':
      case 'BUILD_FAILED':
        return 'bg-error-muted text-error';
      default:
        return 'bg-surface-2 text-text-tertiary';
    }
  }

  function isActiveStatus(status: string | null): boolean {
    return status === 'BUILDING' || status === 'PENDING' || status === 'VALIDATING' || status === 'RUNNING';
  }

  function getMatrixSummary(run: BuildRunDetail): string | null {
    if (!run.builds || run.builds.length === 0) return null;
    if (!run.matrixMode) return null;

    const statusCounts = new Map<string, number>();
    for (const build of run.builds) {
      statusCounts.set(build.status, (statusCounts.get(build.status) || 0) + 1);
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

  function getVariantSummary(run: BuildRunDetail): string {
    if (!run.builds || run.builds.length === 0) return '';
    const variants = new Set(run.builds.map(b => b.variant));
    return Array.from(variants).join(', ');
  }

  function runDuration(run: BuildRunDetail): string {
    if (run.startedAt && run.finishedAt) {
      const duration = new Date(run.finishedAt).getTime() - new Date(run.startedAt).getTime();
      return formatDuration(duration);
    }
    if (run.builds && run.builds.length > 0) {
      const totalSeconds = run.builds.reduce((sum, b) => sum + (b.durationSeconds ?? 0), 0);
      if (totalSeconds > 0) return formatDuration(totalSeconds * 1000);
    }
    return '--';
  }

  // ── Data loading ──────────────────────────────────────────────

  async function loadSummary(): Promise<void> {
    try {
      summary = await fetchBuildSummary();
    } catch {
      // Summary is non-critical, don't set error
    }
  }

  async function loadProducts(): Promise<void> {
    try {
      products = await fetchProductList();
      productOptions = products.map(p => ({ value: p.id, label: p.name }));
    } catch {
      // Non-critical
    }
  }

  async function loadPrPipelines(): Promise<void> {
    try {
      const res = await fetchPrPipelines({
        page: currentPage,
        limit: 20,
        productId: prProductFilter || undefined,
        status: prStatusFilter || undefined,
      });
      prPipelines = res.data;
      pagination = res.pagination;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load PR pipelines';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function loadBuildRuns(): Promise<void> {
    try {
      const res = await fetchBuildRuns({
        page: currentPage,
        limit: 25,
        status: runsStatusFilter || undefined,
        product: runsProductFilter ? (products.find(p => p.id === runsProductFilter)?.name) : undefined,
        productId: runsProductFilter || undefined,
        branch: runsBranchFilter || undefined,
        stage: runsStageFilter ? parseInt(runsStageFilter) : undefined,
        triggerType: runsTriggerFilter || undefined,
      });
      buildRuns = res.data;
      pagination = res.pagination;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load build runs';
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
        status: jobsStatusFilter || undefined,
        triggerTypes: jobsTriggerFilter || undefined,
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
    loadSummary();
    if (viewMode === 'prPipelines') loadPrPipelines();
    else if (viewMode === 'buildRuns') loadBuildRuns();
    else loadBuildJobs();
  }

  function refresh(): void {
    refreshing = true;
    loadData();
  }

  function switchTab(mode: ViewMode): void {
    viewMode = mode;
    currentPage = 1;
    loading = true;
    loadData();
  }

  // ── Trigger form handlers ─────────────────────────────────────

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
      const run = await triggerBuildRun({
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
      goto(`/builds/runs/${run.id}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to trigger build';
    } finally {
      submitting = false;
    }
  }

  // ── Upload modal handlers ────────────────────────────────────

  async function loadUploadProducts(): Promise<void> {
    try {
      uploadProducts = await fetchProductList();
    } catch {
      uploadProducts = [];
    }
  }

  function openUploadModal(productId?: string): void {
    preselectedProductId = productId || null;
    uploadStep = 'details';
    uploadProductId = productId || '';
    uploadBoard = '';
    uploadTarget = '';
    uploadVariant = '';
    uploadVersion = '';
    uploadBranch = '';
    uploadNotes = '';
    uploadBuildId = null;
    uploadedArtifacts = [];
    artifactRole = '';
    artifactProcessor = '';
    showUploadModal = true;
    loadUploadProducts();
  }

  function closeUploadModal(): void {
    showUploadModal = false;
    if (uploadBuildId) {
      loadData();
    }
  }

  async function handleUploadCreate(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    uploadSubmitting = true;
    try {
      const build = await createManualBuild({
        product: uploadProducts.find(p => p.id === uploadProductId)?.name || uploadProductId,
        board: uploadBoard,
        target: uploadTarget,
        variant: uploadVariant,
        branch: uploadBranch,
        versionString: uploadVersion || undefined,
        notes: uploadNotes || undefined,
        productId: uploadProductId,
      });
      uploadBuildId = build.id;
      uploadStep = 'artifacts';
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create build';
    } finally {
      uploadSubmitting = false;
    }
  }

  async function handleArtifactUpload(file: File, role: string, processor: string): Promise<void> {
    if (!uploadBuildId) return;
    uploadingFile = true;
    try {
      const artifactType = file.name.endsWith('.hex') ? 'plaintextHex'
        : file.name.endsWith('.cfw') ? 'encryptedCfw'
        : file.name.endsWith('.json') ? 'manifest'
        : undefined;

      const artifact = await uploadBuildArtifact(uploadBuildId, file, {
        role: role || undefined,
        processor: processor || undefined,
        artifactType,
      });
      uploadedArtifacts = [...uploadedArtifacts, artifact];
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to upload artifact';
    } finally {
      uploadingFile = false;
    }
  }

  // ── Lifecycle ─────────────────────────────────────────────────

  onMount(() => {
    if (!auth.hasPermission('builds:view')) {
      goto('/');
      return;
    }
    loadProducts();
    loadData();

    const interval = setInterval(() => {
      loadData();
    }, 10000);
    return () => clearInterval(interval);
  });

  // Reset page when filters change per view
  $effect(() => {
    if (viewMode === 'prPipelines') {
      const _a = prProductFilter;
      const _b = prStatusFilter;
      currentPage = 1;
    }
  });

  $effect(() => {
    if (viewMode === 'buildRuns') {
      const _a = runsProductFilter;
      const _b = runsStageFilter;
      const _c = runsStatusFilter;
      const _d = runsTriggerFilter;
      const _e = runsBranchFilter;
      currentPage = 1;
    }
  });

  $effect(() => {
    if (viewMode === 'jobs') {
      const _a = jobsStatusFilter;
      const _b = jobsTriggerFilter;
      currentPage = 1;
    }
  });

  $effect(() => {
    const _p = currentPage;
    loadData();
  });
</script>

<svelte:head>
  <title>Builds - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Builds"
      description="Firmware build pipelines -- build, flash, and validate in one flow."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- ── Summary Stats Bar ─────────────────────────────────────── -->
  {#if summary}
    <div class="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <div class="text-2xs font-medium text-text-tertiary">Active Runs</div>
        <div class="mt-1 flex items-center gap-2">
          <span class="text-xl font-semibold tabular-nums text-text-primary">{summary.activeRuns}</span>
          {#if summary.activeRuns > 0}
            <span class="relative flex h-2.5 w-2.5">
              <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
              <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent"></span>
            </span>
          {/if}
        </div>
      </div>
      <div class="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <div class="text-2xs font-medium text-text-tertiary">Queued Jobs</div>
        <div class="mt-1 text-xl font-semibold tabular-nums text-text-primary">{summary.queuedJobs}</div>
      </div>
      <div class="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <div class="text-2xs font-medium text-text-tertiary">Success Rate (24h)</div>
        <div class="mt-1 text-xl font-semibold tabular-nums text-text-primary">
          {summary.successRate24h != null ? `${Math.round(summary.successRate24h)}%` : '--'}
        </div>
      </div>
      <div class="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <div class="text-2xs font-medium text-text-tertiary">Avg Duration</div>
        <div class="mt-1 text-xl font-semibold tabular-nums text-text-primary">
          {summary.avgDurationSeconds != null ? formatDuration(summary.avgDurationSeconds * 1000) : '--'}
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Trigger Form (Build Runs + Jobs tabs) ─────────────────── -->
  {#if showForm && viewMode !== 'prPipelines'}
    <FormCard title="Trigger Build" onClose={resetForm}>
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
            {submitting ? 'Triggering...' : 'Trigger Build'}
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  <!-- ── Tab bar ───────────────────────────────────────────────── -->
  <div class="mb-4 flex items-center gap-0 border-b border-border">
    <button
      onclick={() => switchTab('prPipelines')}
      class="px-4 py-2 text-sm font-medium transition-colors {viewMode === 'prPipelines' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      <span class="flex items-center gap-1.5">
        <GitPullRequest size={14} />
        PR Pipelines
      </span>
    </button>
    <button
      onclick={() => switchTab('buildRuns')}
      class="px-4 py-2 text-sm font-medium transition-colors {viewMode === 'buildRuns' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      <span class="flex items-center gap-1.5">
        <Package size={14} />
        Build Runs
      </span>
    </button>
    <button
      onclick={() => switchTab('jobs')}
      class="px-4 py-2 text-sm font-medium transition-colors {viewMode === 'jobs' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      <span class="flex items-center gap-1.5">
        <Hammer size={14} />
        Build Jobs
      </span>
    </button>

    <!-- Right side: count + refresh + action buttons -->
    <div class="ml-auto flex items-center gap-2">
      <span class="text-2xs text-text-tertiary tabular-nums">
        {pagination.total} result{pagination.total !== 1 ? 's' : ''}
      </span>
      <button
        onclick={refresh}
        disabled={refreshing}
        class="btn btn-sm flex items-center gap-1.5"
        title="Refresh"
        aria-label="Refresh"
      >
        <RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
      </button>
      {#if canManage && viewMode !== 'prPipelines'}
        <button
          onclick={() => openUploadModal()}
          class="btn btn-sm flex items-center gap-1.5"
          title="Upload Build"
          aria-label="Upload Build"
        >
          <Upload size={14} />
          Upload
        </button>
        <button
          onclick={() => { showForm = true; }}
          class="btn btn-sm btn-primary flex items-center gap-1.5"
        >
          <Plus size={14} />
          Trigger
        </button>
      {/if}
    </div>
  </div>

  <!-- ── Filters per view ──────────────────────────────────────── -->
  {#if viewMode === 'prPipelines'}
    <div class="mb-4 flex flex-wrap items-center gap-3">
      {#if productOptions.length > 0}
        <Select
          bind:value={prProductFilter}
          placeholder="All products"
          options={productOptions}
        />
      {/if}
      <Select
        bind:value={prStatusFilter}
        placeholder="All statuses"
        options={PR_STATUS_OPTIONS}
      />
    </div>
  {:else if viewMode === 'buildRuns'}
    <div class="mb-4 flex flex-wrap items-center gap-3">
      {#if productOptions.length > 0}
        <Select
          bind:value={runsProductFilter}
          placeholder="All products"
          options={productOptions}
        />
      {/if}
      <Select
        bind:value={runsStageFilter}
        placeholder="All stages"
        options={STAGE_OPTIONS}
      />
      <Select
        bind:value={runsStatusFilter}
        placeholder="All statuses"
        options={STATUS_OPTIONS}
      />
      <Select
        bind:value={runsTriggerFilter}
        placeholder="All triggers"
        options={TRIGGER_TYPE_OPTIONS}
      />
      <TextInput
        bind:value={runsBranchFilter}
        placeholder="Filter by branch..."
      />
    </div>
  {:else}
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <Select
        bind:value={jobsStatusFilter}
        placeholder="All statuses"
        options={STATUS_OPTIONS}
      />
      <Select
        bind:value={jobsTriggerFilter}
        placeholder="All triggers"
        options={[
          { value: 'worker', label: 'Worker' },
          { value: 'manual', label: 'Manual' },
          { value: 'webhook', label: 'Webhook' },
        ]}
      />
    </div>
  {/if}

  <!-- ── Content ───────────────────────────────────────────────── -->
  {#if loading}
    <LoadingState message="Loading {viewMode === 'prPipelines' ? 'PR pipelines' : viewMode === 'buildRuns' ? 'build runs' : 'build jobs'}..." />

  <!-- ── PR Pipelines View ─────────────────────────────────────── -->
  {:else if viewMode === 'prPipelines'}
    {#if prPipelines.length === 0}
      <EmptyState message="No PR pipelines found." />
    {:else}
      <div class="space-y-2">
        {#each prPipelines as pr (pr.prNumber + '-' + pr.productId)}
          <div class="rounded-lg border border-border bg-surface-0 px-4 py-3 transition-colors hover:bg-surface-1">
            <!-- Top row: PR info -->
            <div class="flex items-start justify-between gap-4 mb-2">
              <div class="flex items-center gap-3 min-w-0 flex-1">
                <GitPullRequest size={16} class="flex-shrink-0 text-text-tertiary" />
                <span class="text-sm font-medium text-text-primary">
                  PR #{pr.prNumber}:
                </span>
                {#if pr.prUrl}
                  <a
                    href={pr.prUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="truncate text-sm text-text-primary hover:text-accent transition-colors"
                    title={pr.prTitle || ''}
                  >
                    {pr.prTitle || 'Untitled'}
                    <ExternalLink size={10} class="inline ml-1 text-text-tertiary" />
                  </a>
                {:else}
                  <span class="truncate text-sm text-text-primary" title={pr.prTitle || ''}>
                    {pr.prTitle || 'Untitled'}
                  </span>
                {/if}
              </div>
              <div class="flex items-center gap-3 text-2xs text-text-tertiary flex-shrink-0">
                {#if pr.prAuthor}
                  <span>{pr.prAuthor}</span>
                {/if}
                <span title={formatDateTime(pr.updatedAt)}>
                  {formatTimeAgo(pr.updatedAt)}
                </span>
              </div>
            </div>

            <!-- Middle row: product + branch info -->
            <div class="flex items-center gap-2 mb-2.5 text-2xs">
              <span class="font-medium text-text-secondary">{pr.product}</span>
              {#if pr.sourceBranch}
                <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-text-secondary">
                  <GitBranch size={10} />
                  {pr.sourceBranch}
                </span>
              {/if}
              {#if pr.targetBranch}
                <span class="text-text-tertiary">&#8594;</span>
                <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-text-tertiary">
                  {pr.targetBranch}
                </span>
              {/if}
              {#if pr.latestCommit}
                <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-text-tertiary font-mono">
                  <GitCommit size={10} />
                  {pr.latestCommit.slice(0, 7)}
                </span>
              {/if}
            </div>

            <!-- Stage badges row -->
            <div class="flex items-center gap-1.5">
              {#each ALL_STAGES as stageNum}
                {@const stageData = pr.stages[stageNum]}
                {@const abbrev = STAGE_ABBREV[stageNum]}
                {@const stageName = STAGE_NAMES[stageNum]}
                {#if stageData}
                  <button
                    onclick={() => goto(`/builds/runs/${stageData.buildRunId}`)}
                    class="inline-flex items-center gap-1 rounded px-2 py-1 text-2xs font-semibold transition-colors hover:opacity-80 {getStageStatusClasses(stageData.status)}"
                    title="{stageName}: {stageData.status} ({stageData.completedBuilds}/{stageData.expectedBuilds} builds){stageData.duration != null ? ' - ' + formatDuration(stageData.duration * 1000) : ''}"
                  >
                    {abbrev}
                    {#if stageData.status === 'SUCCESS' || stageData.status === 'COMPLETED'}
                      <Check size={10} />
                    {:else if isActiveStatus(stageData.status)}
                      <Loader2 size={10} class="animate-spin" />
                    {:else if stageData.status === 'FAILED' || stageData.status === 'BUILD_FAILED'}
                      <X size={10} />
                    {/if}
                  </button>
                {:else}
                  <span
                    class="inline-flex items-center gap-1 rounded px-2 py-1 text-2xs font-semibold bg-surface-2 text-text-tertiary"
                    title="{stageName}: Not triggered"
                  >
                    {abbrev}
                    <span class="text-text-tertiary">&mdash;</span>
                  </span>
                {/if}
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {/if}

  <!-- ── Build Runs View ───────────────────────────────────────── -->
  {:else if viewMode === 'buildRuns'}
    {#if buildRuns.length === 0}
      <EmptyState message="No build runs found." />
    {:else}
      <div class="space-y-2">
        {#each buildRuns as run (run.id)}
          {@const trigger = getTriggerConfig(run.triggerType ?? '')}
          {@const productInfo = getProductInfo(run.product ?? '')}
          <button
            onclick={() => goto(`/builds/runs/${run.id}`)}
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
                <!-- Stage badge -->
                {#if run.stage}
                  {@const modeKey = STAGE_TO_MATRIX_MODE[String(run.stage)]}
                  {#if modeKey && STAGE_BADGE[modeKey]}
                    {@const badge = STAGE_BADGE[modeKey]}
                    {@const stage = STAGE_DISPLAY[modeKey as ValidationStage]}
                    {@const BadgeIcon = badge.icon}
                    <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded {badge.color} text-2xs font-medium" title={stage?.description ?? modeKey}>
                      <BadgeIcon size={10} />
                      {stage?.name ?? modeKey}
                    </span>
                  {/if}
                {:else if run.matrixMode && STAGE_BADGE[run.matrixMode]}
                  {@const badge = STAGE_BADGE[run.matrixMode]}
                  {@const stage = STAGE_DISPLAY[run.matrixMode as ValidationStage]}
                  {@const BadgeIcon = badge.icon}
                  <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded {badge.color} text-2xs font-medium" title={stage?.description ?? run.matrixMode}>
                    <BadgeIcon size={10} />
                    {stage?.name ?? run.matrixMode}
                  </span>
                {/if}
                <!-- PR info -->
                {#if run.prNumber}
                  <span class="inline-flex items-center gap-1 rounded bg-accent-muted px-1.5 py-0.5 text-2xs text-accent font-medium">
                    <GitPullRequest size={10} />
                    #{run.prNumber}
                  </span>
                {/if}
                {#if run.branch}
                  <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
                    <GitBranch size={10} />
                    {run.branch}
                  </span>
                {/if}
                {#if run.commitSha}
                  <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono text-text-tertiary">
                    <GitCommit size={10} />
                    {run.commitSha.slice(0, 7)}
                  </span>
                {/if}
                <StatusBadge status={run.status} />
              </div>
              <div class="flex items-center gap-3 text-2xs text-text-tertiary flex-shrink-0">
                <span class="tabular-nums">{runDuration(run)}</span>
                <span title={formatDateTime(run.createdAt)}>
                  {formatTimeAgo(run.createdAt)}
                </span>
              </div>
            </div>
            <!-- Build info row -->
            <div class="flex items-center gap-3 text-2xs flex-wrap">
              <span class="text-text-tertiary">
                {run.completedBuilds ?? 0}/{run.expectedBuilds ?? 0} builds
              </span>
              <!-- Trigger source badge -->
              {#if run.triggerType}
                {@const triggerBadge = TRIGGER_TYPE_BADGE[run.triggerType] || TRIGGER_TYPE_BADGE.manual}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded {triggerBadge.color} font-medium">
                  {triggerBadge.label}
                </span>
              {/if}
              <!-- Validation indicator -->
              {#if run.validationRunId}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-success-muted text-success font-medium" title="Validation run linked">
                  <FlaskConical size={10} />
                  Validated
                </span>
              {:else if run.autoValidate}
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-muted text-accent font-medium" title="Will auto-trigger validation">
                  <FlaskConical size={10} />
                  Auto
                </span>
              {/if}
              <!-- Build summary -->
              {#if run.builds && run.builds.length > 0}
                {@const matrixSummary = getMatrixSummary(run)}
                {#if matrixSummary}
                  <span class="text-text-tertiary">{matrixSummary}</span>
                {:else}
                  <span class="text-text-tertiary">
                    {getVariantSummary(run)}
                  </span>
                {/if}
              {/if}
              <!-- Build version chips -->
              {#if run.builds && run.builds.length > 0}
                <div class="flex items-center gap-1.5 ml-auto">
                  {#each run.builds.slice(0, 6) as build}
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
                  {#if run.builds.length > 6}
                    <span class="text-2xs text-text-tertiary">+{run.builds.length - 6}</span>
                  {/if}
                </div>
              {/if}
            </div>
          </button>
        {/each}
      </div>
    {/if}

  <!-- ── Build Jobs View ───────────────────────────────────────── -->
  {:else}
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
                {#if build.triggerTypes && build.triggerTypes !== 'worker'}
                  {@const triggerBadge = TRIGGER_TYPE_BADGE[build.triggerTypes] || TRIGGER_TYPE_BADGE.worker}
                  <span class="inline-flex items-center rounded px-1.5 py-0.5 text-2xs font-medium {triggerBadge.color}">
                    {triggerBadge.label}
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
  {/if}

  <!-- ── Pagination ────────────────────────────────────────────── -->
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
          title="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          aria-label="Previous page"
          title="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.min(pagination.pages, currentPage + 1))}
          disabled={currentPage >= pagination.pages}
          aria-label="Next page"
          title="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (currentPage = pagination.pages)}
          disabled={currentPage >= pagination.pages}
          aria-label="Last page"
          title="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>

<!-- ── Upload Build Modal ──────────────────────────────────────── -->
<Modal open={showUploadModal} title={uploadStep === 'details' ? 'Upload Build' : 'Upload Artifacts'} onclose={closeUploadModal} size="lg">
  {#if uploadStep === 'details'}
    <form onsubmit={handleUploadCreate} class="space-y-3">
      <Select
        bind:value={uploadProductId}
        label="Product"
        placeholder="Select product"
        options={uploadProducts.map(p => ({ value: p.id, label: p.name }))}
        required
        disabled={!!preselectedProductId}
      />
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <TextInput bind:value={uploadBoard} label="Board" placeholder="e.g. alpha_b0" required />
        <Select
          bind:value={uploadTarget}
          label="Target"
          placeholder="Select target"
          options={[
            { value: 'app', label: 'App' },
            { value: 'mfg', label: 'Manufacturing' },
          ]}
          required
        />
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select
          bind:value={uploadVariant}
          label="Variant"
          placeholder="Select variant"
          options={[
            { value: 'debug', label: 'Debug' },
            { value: 'release', label: 'Release' },
          ]}
          required
        />
        <TextInput bind:value={uploadVersion} label="Version" placeholder="e.g. 0.8.3" />
      </div>
      <TextInput bind:value={uploadBranch} label="Branch" placeholder="e.g. main" required />
      <div>
        <label for="upload-notes" class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
        <textarea
          id="upload-notes"
          bind:value={uploadNotes}
          placeholder="Optional notes about this build..."
          rows="2"
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
        ></textarea>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button type="button" onclick={closeUploadModal} class="btn btn-sm">Cancel</button>
        <button type="submit" disabled={uploadSubmitting} class="btn btn-sm btn-primary">
          {uploadSubmitting ? 'Creating...' : 'Create Build'}
        </button>
      </div>
    </form>
  {:else}
    <!-- Artifact upload step -->
    <div class="space-y-4">
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="text-2xs text-text-tertiary mb-1">Build created</div>
        <div class="text-sm font-mono text-text-primary">{uploadBuildId?.slice(0, 12)}</div>
      </div>

      {#if uploadedArtifacts.length > 0}
        <div>
          <div class="text-2xs font-medium text-text-tertiary mb-2">Uploaded ({uploadedArtifacts.length})</div>
          <div class="space-y-1">
            {#each uploadedArtifacts as artifact}
              <div class="flex items-center gap-2 rounded border border-border bg-surface-0 px-3 py-1.5 text-sm">
                <span class="flex-1 font-mono text-text-primary truncate">{artifact.name}</span>
                <span class="text-2xs text-success">Uploaded</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="rounded-lg border-2 border-dashed border-border bg-surface-0 p-4">
        <div class="text-sm font-medium text-text-primary mb-3">Add Artifact</div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-3">
          <Select
            bind:value={artifactRole}
            label="Role"
            placeholder="Select role"
            options={[
              { value: 'app', label: 'App' },
              { value: 'comms', label: 'Comms' },
              { value: 'modem', label: 'Modem' },
            ]}
          />
          <Select
            bind:value={artifactProcessor}
            label="Processor"
            placeholder="Select processor"
            options={[
              { value: 'nrf52840', label: 'nRF52840' },
              { value: 'nrf9151', label: 'nRF9151' },
            ]}
          />
        </div>
        <label
          for="upload-artifact-file"
          class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-border p-4 transition-colors hover:border-text-tertiary hover:bg-surface-1"
        >
          <Upload size={20} class="text-text-tertiary" />
          <span class="text-2xs text-text-tertiary">
            {uploadingFile ? 'Uploading...' : 'Click to select .hex or .cfw file'}
          </span>
          <input
            id="upload-artifact-file"
            type="file"
            accept=".hex,.cfw,.bin,.json"
            class="hidden"
            disabled={uploadingFile}
            onchange={(e) => {
              const input = e.target as HTMLInputElement;
              const file = input.files?.[0];
              if (file) {
                handleArtifactUpload(file, artifactRole, artifactProcessor);
              }
              input.value = '';
            }}
          />
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <button onclick={closeUploadModal} class="btn btn-sm btn-primary">
          Done
        </button>
      </div>
    </div>
  {/if}
</Modal>
