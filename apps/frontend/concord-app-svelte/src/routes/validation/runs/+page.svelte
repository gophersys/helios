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
    Shield,
    Zap,
    FlaskConical,
    Flame,
    Play,
    AlertCircle,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ValidationRun, ValidationTrigger, ValidationStage, Product, Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import PlanesLoader from '$lib/components/ui/planes-loader.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import { BitbucketIcon } from '$lib/components/icons';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('validation:manage'));

  // Tab options
  type TabType = 'active' | 'failed' | 'all';
  let activeTab = $state<TabType>('all');

  const VARIANT_OPTIONS = [
    { value: 'debug', label: 'Debug' },
    { value: 'release', label: 'Release' },
    { value: 'mfg', label: 'Manufacturing' },
  ];

  const STAGE_OPTIONS = [
    { value: 'gate', label: 'Gate Tests' },
    { value: 'smoke', label: 'Smoke' },
    { value: 'integration', label: 'Integration' },
    { value: 'nightly', label: 'Nightly' },
  ];

  // List state
  let runs = $state<ValidationRun[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let page = $state(1);

  // Search
  let searchQuery = $state('');

  // Create form state
  let showForm = $state(false);
  let formName = $state('');
  let formProductId = $state('');
  let formNodeId = $state('');
  let formSerialNumber = $state('');
  let formVariant = $state('');
  let formStage = $state('gate');
  let formNotes = $state('');
  let submitting = $state(false);

  // Dropdown options
  let products = $state<{ value: string; label: string }[]>([]);
  let nodes = $state<{ value: string; label: string }[]>([]);

  // Counts for tabs
  const activeCount = $derived(runs.filter(r => r.status === 'ACTIVE').length);
  const failedCount = $derived(runs.filter(r => r.status === 'COMPLETED' && (r.failedCount ?? 0) > 0).length);

  // Filter and sort runs based on tab and search
  const filteredRuns = $derived.by(() => {
    let result = runs;

    // Filter by tab
    if (activeTab === 'active') {
      result = result.filter(r => r.status === 'ACTIVE');
    } else if (activeTab === 'failed') {
      result = result.filter(r => r.status === 'COMPLETED' && (r.failedCount ?? 0) > 0);
    }

    // Filter by search
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

    // Smart sorting: active first, then failed, then passed
    return result.sort((a, b) => {
      // Active always first
      if (a.status === 'ACTIVE' && b.status !== 'ACTIVE') return -1;
      if (b.status === 'ACTIVE' && a.status !== 'ACTIVE') return 1;

      // Then by recency
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });
  });

  // Helper functions
  function getTrigger(run: ValidationRun): ValidationTrigger {
    if (run.trigger) return run.trigger;
    const config = run.config as Record<string, unknown> | null;
    if (config?.bitbucketPrId || config?.pullRequestId) return 'bitbucket';
    if (config?.nightlyRun || config?.scheduled) return 'nightly';
    if (config?.pipelineId) return 'ci';
    return 'manual';
  }

  function getStage(run: ValidationRun): ValidationStage {
    if (run.stage) return run.stage;
    const config = run.config as Record<string, unknown> | null;
    if (config?.stage) return config.stage as ValidationStage;
    const name = run.name.toLowerCase();
    if (name.includes('gate')) return 'gate';
    if (name.includes('nightly')) return 'nightly';
    if (name.includes('integration')) return 'integration';
    if (name.includes('smoke')) return 'smoke';
    return 'gate';
  }

  function getTriggerContext(run: ValidationRun): { icon: typeof BitbucketIcon | typeof Moon | typeof Hand | typeof GitBranch; text: string; iconClass: string } {
    const trigger = getTrigger(run);
    const config = run.config as Record<string, unknown> | null;

    switch (trigger) {
      case 'bitbucket': {
        const prId = config?.bitbucketPrId || config?.pullRequestId || '';
        const prTitle = config?.prTitle || config?.commitMessage || '';
        return {
          icon: BitbucketIcon,
          text: prId ? `PR #${prId}${prTitle ? `: ${prTitle}` : ''}` : 'Bitbucket PR',
          iconClass: 'text-blue-400'
        };
      }
      case 'nightly':
      case 'scheduled':
        return {
          icon: Moon,
          text: 'Scheduled nightly run',
          iconClass: 'text-purple-400'
        };
      case 'ci': {
        const pipelineId = config?.pipelineId || '';
        return {
          icon: GitBranch,
          text: pipelineId ? `CI Pipeline #${pipelineId}` : 'CI Pipeline',
          iconClass: 'text-orange-400'
        };
      }
      default:
        return {
          icon: Hand,
          text: run.createdBy ? `Manual run by ${run.createdBy.name}` : 'Manual run',
          iconClass: 'text-text-tertiary'
        };
    }
  }

  function getStageDisplay(stage: ValidationStage): { label: string; icon: typeof Shield; colorClass: string; bgClass: string } {
    switch (stage) {
      case 'gate':
        return { label: 'GATE TESTS', icon: Shield, colorClass: 'text-accent', bgClass: 'bg-accent' };
      case 'nightly':
        return { label: 'NIGHTLY', icon: Moon, colorClass: 'text-purple-400', bgClass: 'bg-purple-500' };
      case 'integration':
        return { label: 'INTEGRATION', icon: FlaskConical, colorClass: 'text-blue-400', bgClass: 'bg-blue-500' };
      case 'smoke':
        return { label: 'SMOKE', icon: Flame, colorClass: 'text-orange-400', bgClass: 'bg-orange-500' };
      default:
        return { label: 'CUSTOM', icon: Zap, colorClass: 'text-text-secondary', bgClass: 'bg-surface-3' };
    }
  }

  function getStatusDisplay(run: ValidationRun): { label: string; icon: typeof CheckCircle2; colorClass: string } {
    if (run.status === 'ACTIVE') {
      return { label: 'RUNNING', icon: Loader2, colorClass: 'text-accent' };
    }
    if (run.status === 'CANCELLED') {
      return { label: 'CANCELLED', icon: XCircle, colorClass: 'text-text-tertiary' };
    }
    if ((run.failedCount ?? 0) > 0) {
      return { label: 'FAILED', icon: XCircle, colorClass: 'text-error' };
    }
    return { label: 'PASSED', icon: CheckCircle2, colorClass: 'text-success' };
  }

  function getProgressPercent(run: ValidationRun): number {
    if (!run.targetCount) return 0;
    return Math.round(((run.passedCount ?? 0) + (run.failedCount ?? 0)) / run.targetCount * 100);
  }

  function getDuration(run: ValidationRun): string | null {
    if (!run.startedAt) return null;
    const start = new Date(run.startedAt).getTime();
    const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
    return formatDuration(end - start);
  }

  function getFailedTests(run: ValidationRun): string[] {
    // Extract from executions if available
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
    loading = true;
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '50');

      const res = await apiFetch<ApiResponse<{ data: ValidationRun[]; pagination: Pagination }>>(
        '/v2/validation/runs?' + params.toString()
      );

      runs = res.data.data;
      pagination = res.data.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load validation runs';
    } finally {
      loading = false;
    }
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
    } catch {
      // Dropdowns fail silently
    }
  }

  function resetForm(): void {
    formName = '';
    formProductId = '';
    formNodeId = '';
    formSerialNumber = '';
    formVariant = '';
    formStage = 'gate';
    formNotes = '';
    showForm = false;
  }

  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;

    const body: Record<string, unknown> = {
      name: formName,
      productId: formProductId,
      nodeId: formNodeId,
      serialNumber: formSerialNumber,
    };
    if (formVariant) body.firmwareVariant = formVariant;
    if (formStage) body.stage = formStage;
    if (formNotes.trim()) body.notes = formNotes.trim();

    try {
      const res = await api.post<ApiResponse<ValidationRun>>('/v2/validation/runs', body);
      resetForm();
      await fetchRuns();
      if (res.data?.id) {
        goto(`/validation/runs/${res.data.id}`);
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create run';
    } finally {
      submitting = false;
    }
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) {
      goto('/');
      return;
    }
    fetchRuns();
  });

  $effect(() => {
    const _p = page;
    fetchRuns();
  });
</script>

<svelte:head>
  <title>Validation Runs — Concord</title>
</svelte:head>

<div class="space-y-4">
  <!-- Header -->
  <div class="flex items-start justify-between">
    <div>
      <h1 class="text-xl font-semibold text-text-primary">Validation Runs</h1>
      <p class="text-sm text-text-tertiary mt-0.5">Hardware test results for firmware validation</p>
    </div>
    {#if canManage}
      <button
        onclick={() => { showForm = true; fetchDropdowns(); }}
        class="btn btn-sm btn-primary flex items-center gap-1.5"
      >
        <Plus size={14} />
        New Run
      </button>
    {/if}
  </div>

  <ErrorAlert message={error} />

  <!-- Create form -->
  {#if showForm}
    <FormCard title="New Validation Run" onClose={resetForm}>
      <form onsubmit={handleSubmit} class="space-y-3">
        <TextInput bind:value={formName} label="Name" placeholder="e.g. Alpha Gate v0.5.1 PR-123" required />

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Select
            bind:value={formProductId}
            label="Product"
            placeholder="Select product"
            options={products}
            required
          />
          <Select
            bind:value={formNodeId}
            label="MTIB Node"
            placeholder="Select node"
            options={nodes}
            required
          />
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <TextInput bind:value={formSerialNumber} label="Serial Number" placeholder="70B3D584C01E1FCC" required />
          <Select
            bind:value={formVariant}
            label="Firmware Variant"
            placeholder="Any variant"
            options={VARIANT_OPTIONS}
          />
          <Select
            bind:value={formStage}
            label="Test Stage"
            options={STAGE_OPTIONS}
          />
        </div>

        <div>
          <label for="notes" class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
          <textarea
            id="notes"
            bind:value={formNotes}
            rows={2}
            placeholder="Optional notes..."
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

  <!-- Tabs and Search -->
  <div class="flex items-center justify-between gap-4">
    <!-- Tabs -->
    <div class="flex items-center gap-1 p-1 rounded-lg bg-surface-1">
      <button
        onclick={() => { activeTab = 'active'; }}
        class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5
          {activeTab === 'active' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-secondary hover:text-text-primary'}"
      >
        <Loader2 size={14} class={activeTab === 'active' ? 'text-accent' : ''} />
        Active
        {#if activeCount > 0}
          <span class="px-1.5 py-0.5 rounded-full text-2xs bg-accent text-white">{activeCount}</span>
        {/if}
      </button>
      <button
        onclick={() => { activeTab = 'failed'; }}
        class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5
          {activeTab === 'failed' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-secondary hover:text-text-primary'}"
      >
        <XCircle size={14} class={activeTab === 'failed' ? 'text-error' : ''} />
        Failed
        {#if failedCount > 0}
          <span class="px-1.5 py-0.5 rounded-full text-2xs bg-error text-white">{failedCount}</span>
        {/if}
      </button>
      <button
        onclick={() => { activeTab = 'all'; }}
        class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors
          {activeTab === 'all' ? 'bg-surface-0 text-text-primary shadow-sm' : 'text-text-secondary hover:text-text-primary'}"
      >
        All Runs
      </button>
    </div>

    <!-- Search -->
    <div class="relative">
      <Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Search version, PR, test..."
        class="pl-9 pr-3 py-1.5 w-64 text-sm rounded-lg border border-border bg-surface-0 text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
      />
    </div>
  </div>

  <!-- Runs list -->
  {#if loading}
    <PlanesLoader message="Loading validation runs..." />
  {:else if filteredRuns.length === 0}
    <EmptyState message={searchQuery ? 'No runs match your search.' : activeTab === 'active' ? 'No active runs.' : activeTab === 'failed' ? 'No failed runs. Nice!' : 'No validation runs yet.'} />
  {:else}
    <div class="space-y-3">
      {#each filteredRuns as run (run.id)}
        {@const stage = getStage(run)}
        {@const stageDisplay = getStageDisplay(stage)}
        {@const statusDisplay = getStatusDisplay(run)}
        {@const triggerContext = getTriggerContext(run)}
        {@const config = run.config as Record<string, unknown> | null}
        {@const failedTests = getFailedTests(run)}
        {@const currentTest = getCurrentTest(run)}
        {@const progressPct = getProgressPercent(run)}

        <!-- Run Card -->
        <button
          onclick={() => goto(`/validation/runs/${run.id}`)}
          class="w-full text-left rounded-xl border border-border bg-surface-0 overflow-hidden hover:border-accent/50 hover:shadow-lg transition-all group"
        >
          <!-- Card Header: Stage + Status -->
          <div class="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
            <div class="flex items-center gap-2">
              <svelte:component this={stageDisplay.icon} size={14} class={stageDisplay.colorClass} />
              <span class="text-xs font-bold tracking-wide {stageDisplay.colorClass}">
                {stageDisplay.label}
              </span>
              <span class="text-xs font-bold {statusDisplay.colorClass}">
                {statusDisplay.label}
              </span>
              {#if run.status === 'ACTIVE'}
                <svelte:component this={Loader2} size={12} class="text-accent animate-spin" />
              {/if}
            </div>
            <span class="text-2xs text-text-tertiary" title={formatDateTime(run.createdAt)}>
              {formatTimeAgo(run.createdAt)}
            </span>
          </div>

          <!-- Card Body -->
          <div class="px-4 py-3 space-y-3">
            <!-- Trigger Context -->
            <div class="flex items-center gap-2 text-sm">
              <svelte:component this={triggerContext.icon} size={16} class={triggerContext.iconClass} />
              <span class="text-text-primary font-medium truncate">{triggerContext.text}</span>
            </div>

            <!-- Hardware Context -->
            <div class="flex items-center gap-2 text-xs text-text-secondary">
              <Package size={12} class="text-text-tertiary" />
              <span>{run.product?.name || 'Unknown Product'}</span>
              <span class="text-text-tertiary">•</span>
              <span class="font-mono">{config?.firmwareVersion || config?.firmwareVariant || 'v?.?.?'}-{config?.firmwareVariant || 'debug'}</span>
              <span class="text-text-tertiary">•</span>
              <span class="font-mono text-text-tertiary">{config?.serialNumber || '—'}</span>
            </div>

            <!-- Progress Bar -->
            <div class="space-y-1">
              <div class="flex items-center justify-between text-xs">
                <div class="flex items-center gap-3">
                  <span class="flex items-center gap-1">
                    <CheckCircle2 size={12} class="text-success" />
                    <span class="text-text-primary font-medium">{run.passedCount ?? 0}</span>
                  </span>
                  <span class="flex items-center gap-1 {(run.failedCount ?? 0) > 0 ? 'text-error' : 'text-text-tertiary'}">
                    <XCircle size={12} />
                    <span class="font-medium">{run.failedCount ?? 0}</span>
                  </span>
                  <span class="text-text-tertiary">/ {run.targetCount ?? 0} tests</span>
                </div>
                {#if getDuration(run)}
                  <span class="flex items-center gap-1 text-text-tertiary">
                    <Clock size={12} />
                    {getDuration(run)}
                  </span>
                {/if}
              </div>
              <div class="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500 {(run.failedCount ?? 0) > 0 ? 'bg-error' : run.status === 'ACTIVE' ? 'bg-accent' : 'bg-success'}"
                  style="width: {progressPct}%"
                ></div>
              </div>
            </div>

            <!-- Failed Tests or Current Test -->
            {#if failedTests.length > 0}
              <div class="flex items-start gap-2 text-xs">
                <AlertCircle size={12} class="text-error mt-0.5 flex-shrink-0" />
                <div class="flex flex-wrap gap-1">
                  {#each failedTests as testName}
                    <span class="px-1.5 py-0.5 rounded bg-error/10 text-error font-mono">{testName}</span>
                  {/each}
                  {#if (run.failedCount ?? 0) > 3}
                    <span class="px-1.5 py-0.5 rounded bg-error/10 text-error">+{(run.failedCount ?? 0) - 3} more</span>
                  {/if}
                </div>
              </div>
            {:else if run.status === 'ACTIVE' && currentTest}
              <div class="flex items-center gap-2 text-xs">
                <Play size={12} class="text-accent" />
                <span class="text-text-secondary">Running:</span>
                <span class="font-mono text-text-primary">{currentTest}</span>
              </div>
            {/if}
          </div>

          <!-- Hover indicator -->
          <div class="h-0.5 bg-accent scale-x-0 group-hover:scale-x-100 transition-transform origin-left"></div>
        </button>
      {/each}
    </div>
  {/if}

  <!-- Pagination -->
  {#if pagination.pages > 1}
    <div class="flex items-center justify-between pt-2">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages} · {pagination.total} runs
      </span>
      <div class="flex items-center gap-1">
        <button
          onclick={() => (page = 1)}
          disabled={page <= 1}
          aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (page = Math.min(pagination.pages, page + 1))}
          disabled={page >= pagination.pages}
          aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (page = pagination.pages)}
          disabled={page >= pagination.pages}
          aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
    </div>
  {/if}
</div>
