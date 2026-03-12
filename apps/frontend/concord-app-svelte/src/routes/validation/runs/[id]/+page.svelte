<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import {
    ArrowLeft,
    Ban,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Circle,
    Clock,
    Cpu,
    Download,
    FileText,
    GitCompareArrows,
    Loader2,
    Package,
    Play,
    SkipForward,
    XCircle,
    Zap,
    Terminal,
    Layers,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ValidationRun, ValidationExecution } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import {
    subscribeValidationRun,
    type ValidationTestStartEvent,
    type ValidationTestResultEvent,
    type ValidationRunFinishEvent,
  } from '$lib/services/websocket';

  const auth = getAuth();
  const runId = $derived($page.params.id);

  let run = $state<ValidationRun | null>(null);
  let executions = $state<ValidationExecution[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let cancelling = $state(false);
  let triggering = $state(false);
  let showTrigger = $state(false);
  let triggerFwVersion = $state('');
  let pollInterval: ReturnType<typeof setInterval> | null = null;
  let unsubscribeWs: (() => void) | null = null;

  // Live test timeline state (from WebSocket)
  interface LiveTest {
    name: string;
    module: string | null;
    status: 'queued' | 'running' | 'passed' | 'failed' | 'skipped';
    durationS: number | null;
    errorMessage: string | null;
    measurements: Record<string, unknown> | null;
    logOutput: string | null;
    expanded: boolean;
  }
  let liveTests = $state<LiveTest[]>([]);
  let liveRunning = $state(false);
  let liveFinished = $state(false);
  let liveSummary = $state<{ total: number; passed: number; failed: number; errors: number; durationS: number | null } | null>(null);

  // Artifacts
  interface Artifact {
    name: string;
    objectName: string;
    size: number;
    lastModified: string | null;
    contentType: string | null;
  }
  let artifacts = $state<Artifact[]>([]);
  let artifactsLoading = $state(false);
  let logContent = $state<string | null>(null);
  let logArtifactName = $state<string | null>(null);

  // Build jobs from pipeline
  interface BuildJob {
    id: string;
    product: string;
    fwType: string;
    variant: string;
    status: string;
    commitSha: string | null;
    branch: string;
    logOutput: string | null;
    errorMessage: string | null;
    durationSeconds: number | null;
    expanded: boolean;
  }
  let buildJobs = $state<BuildJob[]>([]);

  // Simulating demo
  let simulating = $state(false);

  // GitHub Actions style: selected stage/job
  let selectedStage = $state<string | null>(null);

  const isActive = $derived(run?.status === 'ACTIVE');

  const progressPct = $derived.by(() => {
    if (!run || !run.targetCount) return 0;
    return Math.round((run.completedCount / run.targetCount) * 100);
  });

  const durationMs = $derived.by(() => {
    if (!run?.startedAt) return null;
    const start = new Date(run.startedAt).getTime();
    const end = run.finishedAt ? new Date(run.finishedAt).getTime() : Date.now();
    return end - start;
  });

  const serialNumber = $derived(
    (run?.config as Record<string, unknown> | null)?.serialNumber as string | undefined
  );
  const firmwareVariant = $derived(
    (run?.config as Record<string, unknown> | null)?.firmwareVariant as string | undefined
  );

  // Stage type: can be tests or builds
  interface Stage {
    name: string;
    type: 'build' | 'test';
    tests: LiveTest[];
    builds: BuildJob[];
    passed: number;
    failed: number;
    skipped: number;
    running: number;
    durationS: number;
  }

  // Group tests by module/stage for GitHub Actions style sidebar
  const stages = $derived.by(() => {
    const stageList: Stage[] = [];

    // Add Build stage if there are build jobs
    if (buildJobs.length > 0) {
      let passed = 0, failed = 0, running = 0, durationS = 0;
      for (const b of buildJobs) {
        if (b.status === 'SUCCESS') passed++;
        else if (b.status === 'FAILED') failed++;
        else if (b.status === 'BUILDING') running++;
        if (b.durationSeconds) durationS += b.durationSeconds;
      }
      stageList.push({
        name: 'Build',
        type: 'build',
        tests: [],
        builds: buildJobs,
        passed,
        failed,
        skipped: 0,
        running,
        durationS,
      });
    }

    // Add test stages
    const stageMap = new Map<string, Stage>();

    for (const test of liveTests) {
      const stageName = test.module || 'Tests';
      if (!stageMap.has(stageName)) {
        stageMap.set(stageName, {
          name: stageName,
          type: 'test',
          tests: [],
          builds: [],
          passed: 0,
          failed: 0,
          skipped: 0,
          running: 0,
          durationS: 0,
        });
      }
      const stage = stageMap.get(stageName)!;
      stage.tests.push(test);
      if (test.status === 'passed') stage.passed++;
      else if (test.status === 'failed') stage.failed++;
      else if (test.status === 'skipped') stage.skipped++;
      else if (test.status === 'running') stage.running++;
      if (test.durationS) stage.durationS += test.durationS;
    }

    stageList.push(...Array.from(stageMap.values()));
    return stageList;
  });

  // Auto-select first stage or stage with running/failed tests
  $effect(() => {
    if (stages.length > 0 && !selectedStage) {
      // Prefer stage with running tests, then failed, then first
      const runningStage = stages.find(s => s.running > 0);
      const failedStage = stages.find(s => s.failed > 0);
      selectedStage = runningStage?.name || failedStage?.name || stages[0].name;
    }
  });

  // Tests for the selected stage
  const selectedStageData = $derived(
    stages.find(s => s.name === selectedStage) || null
  );

  // Live counts for summary
  const livePassedCount = $derived(liveTests.filter(t => t.status === 'passed').length);
  const liveFailedCount = $derived(liveTests.filter(t => t.status === 'failed').length);
  const liveSkippedCount = $derived(liveTests.filter(t => t.status === 'skipped').length);
  const liveCompletedCount = $derived(livePassedCount + liveFailedCount + liveSkippedCount);

  async function fetchRun(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<ValidationRun>>(`/v2/validation/runs/${runId}`);
      run = res.data;
      error = null;

      // Hydrate build jobs from pipeline if present
      const pipelineRun = (res.data as any).pipelineRun;
      if (pipelineRun?.builds?.length) {
        buildJobs = pipelineRun.builds.map((b: any) => ({
          id: b.id,
          product: b.product,
          fwType: b.fwType,
          variant: b.variant,
          status: b.status,
          commitSha: b.commitSha,
          branch: b.branch,
          logOutput: b.logOutput,
          errorMessage: b.errorMessage,
          durationSeconds: b.durationSeconds,
          expanded: false,
        }));
      }

      // Hydrate liveTests from executions (for page reload)
      // Only hydrate if liveTests is empty (WebSocket hasn't populated it yet)
      const executions = (res.data as any).executions as any[] | undefined;
      if (executions?.length && liveTests.length === 0) {
        const hydratedTests: LiveTest[] = [];
        for (const ex of executions) {
          const testName = ex.test?.name || 'Unknown';
          const module = ex.test?.category || null;
          let status: LiveTest['status'] = 'queued';
          if (ex.status === 'RUNNING') status = 'running';
          else if (ex.status === 'PASSED') status = 'passed';
          else if (ex.status === 'FAILED') status = 'failed';
          else if (ex.status === 'SKIPPED') status = 'skipped';

          // Extract log output from first result if present
          let logOutput: string | null = null;
          let errorMessage: string | null = null;
          let measurements: Record<string, unknown> | null = null;
          let durationS: number | null = null;

          if (ex.results?.length) {
            const result = ex.results[0].result || {};
            logOutput = result.logOutput || null;
            errorMessage = result.errorMessage || null;
            measurements = result.measurements || null;
            durationS = result.durationS || null;
          }

          // Calculate duration from timestamps if not in result
          if (durationS === null && ex.startedAt && ex.finishedAt) {
            const start = new Date(ex.startedAt).getTime();
            const end = new Date(ex.finishedAt).getTime();
            durationS = (end - start) / 1000;
          }

          hydratedTests.push({
            name: testName,
            module,
            status,
            durationS,
            errorMessage,
            measurements,
            logOutput,
            expanded: status === 'failed', // Auto-expand failures
          });
        }
        liveTests = hydratedTests;

        // Check if run is finished
        if (res.data.status === 'COMPLETED' || res.data.status === 'CANCELLED') {
          liveFinished = true;
        }
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load run';
    } finally {
      loading = false;
    }
  }

  async function cancelRun(): Promise<void> {
    cancelling = true;
    try {
      await api.post(`/v2/validation/runs/${runId}/cancel`);
      fetchRun();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to cancel run';
    } finally {
      cancelling = false;
    }
  }

  async function triggerRun(): Promise<void> {
    triggering = true;
    try {
      await api.post(`/v2/validation/runs/${runId}/trigger`, {
        firmwareVersion: triggerFwVersion.trim(),
      });
      showTrigger = false;
      triggerFwVersion = '';
      fetchRun();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to trigger run';
    } finally {
      triggering = false;
    }
  }

  async function startDemo(scenario: string): Promise<void> {
    simulating = true;
    liveTests = [];
    liveRunning = false;
    liveFinished = false;
    liveSummary = null;
    selectedStage = null;

    try {
      await api.post(`/v2/validation/runs/${runId}/demo/simulate?speed=0.1&scenario=${scenario}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to start demo';
      simulating = false;
    }
  }

  async function fetchArtifacts(): Promise<void> {
    artifactsLoading = true;
    try {
      const res = await apiFetch<ApiResponse<Artifact[]>>(`/v2/validation/runs/${runId}/artifacts`);
      artifacts = res.data;
    } catch {
      artifacts = [];
    } finally {
      artifactsLoading = false;
    }
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function isLogFile(name: string): boolean {
    return /\.(log|txt|uart|csv)$/i.test(name);
  }

  async function viewLog(artifact: Artifact): Promise<void> {
    if (logArtifactName === artifact.name) {
      logContent = null;
      logArtifactName = null;
      return;
    }
    try {
      const res = await fetch(`/v2/validation/runs/${runId}/artifacts/${artifact.name}`);
      if (res.redirected) {
        const textRes = await fetch(res.url);
        logContent = await textRes.text();
      } else {
        logContent = await res.text();
      }
      logArtifactName = artifact.name;
    } catch {
      logContent = 'Failed to load log file.';
      logArtifactName = artifact.name;
    }
  }

  function toggleTestExpanded(testName: string): void {
    const test = liveTests.find(t => t.name === testName);
    if (test) test.expanded = !test.expanded;
  }

  function setupWebSocket(): void {
    if (!runId) return;
    unsubscribeWs = subscribeValidationRun(
      runId,
      {
        onRunStart: () => {
          liveRunning = true;
          liveFinished = false;
        },
        onTestStart: (data: ValidationTestStartEvent) => {
          liveRunning = true;
          const existing = liveTests.find(t => t.name === data.testName);
          if (existing) {
            existing.status = 'running';
          } else {
            liveTests.push({
              name: data.testName,
              module: data.module,
              status: 'running',
              durationS: null,
              errorMessage: null,
              measurements: null,
              logOutput: null,
              expanded: false,
            });
            liveTests = liveTests;
          }
          // Auto-select the stage with running test
          if (data.module && data.module !== selectedStage) {
            selectedStage = data.module;
          }
        },
        onTestResult: (data: ValidationTestResultEvent) => {
          const existing = liveTests.find(t => t.name === data.testName);
          if (existing) {
            existing.status = data.skipped ? 'skipped' : data.passed ? 'passed' : 'failed';
            existing.durationS = data.durationS;
            existing.errorMessage = data.errorMessage;
            existing.measurements = data.measurements;
            existing.logOutput = data.logOutput;
            // Auto-expand failures
            if (!data.passed && !data.skipped) existing.expanded = true;
            liveTests = liveTests;
          }
        },
        onRunFinish: (data: ValidationRunFinishEvent) => {
          liveRunning = false;
          liveFinished = true;
          simulating = false;
          liveSummary = {
            total: data.total,
            passed: data.passed,
            failed: data.failed,
            errors: data.errors,
            durationS: data.durationS,
          };
          fetchRun();
        },
      },
      (msg) => {
        console.warn('Validation WebSocket error:', msg);
      }
    );
  }

  function cleanup(): void {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    if (unsubscribeWs) {
      unsubscribeWs();
      unsubscribeWs = null;
    }
  }

  function getStageStatusIcon(stage: typeof stages[0]) {
    if (stage.running > 0) return { icon: Loader2, class: 'text-accent animate-spin' };
    if (stage.failed > 0) return { icon: XCircle, class: 'text-error' };
    if (stage.passed > 0 && stage.failed === 0) return { icon: CheckCircle2, class: 'text-success' };
    return { icon: Circle, class: 'text-text-tertiary' };
  }

  onMount(() => {
    if (!auth.hasPermission('validation:view')) {
      goto('/');
      return;
    }
    fetchRun();
    fetchArtifacts();
    setupWebSocket();

    pollInterval = setInterval(() => {
      if (run?.status === 'ACTIVE' && !liveRunning) fetchRun();
    }, 5000);
  });

  onDestroy(cleanup);
  beforeNavigate(cleanup);
</script>

<svelte:head>
  <title>{run?.name ?? 'Run'} — Validation — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <!-- Back link -->
  <button
    onclick={() => goto('/validation/runs')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    Validation Runs
  </button>

  {#if loading}
    <LoadingState message="Loading run..." />
  {:else if error && !run}
    <ErrorAlert message={error} />
  {:else if run}
    <ErrorAlert message={error} />

    <!-- Header -->
    <div class="flex items-start justify-between gap-4 mb-4">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-lg font-semibold text-text-primary">{run.name}</h1>
          <StatusBadge status={run.status} />
          {#if liveRunning}
            <span class="inline-flex items-center gap-1.5 rounded-full bg-success-muted px-2 py-0.5 text-2xs font-medium text-success">
              <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
              </span>
              LIVE
            </span>
          {/if}
        </div>
        <div class="mt-1 flex items-center gap-4 text-xs text-text-tertiary">
          {#if run.product}
            <span>{run.product.name}</span>
          {/if}
          {#if serialNumber}
            <span class="font-mono">{serialNumber}</span>
          {/if}
          {#if firmwareVariant}
            <span class="capitalize">{firmwareVariant}</span>
          {/if}
          {#if run.createdBy}
            <span>by {run.createdBy.name}</span>
          {/if}
        </div>
      </div>

      <div class="flex items-center gap-2">
        <!-- Demo buttons -->
        <div class="flex items-center gap-1">
          <button
            onclick={() => startDemo('happy')}
            disabled={simulating}
            class="btn btn-sm flex items-center gap-1.5 text-success"
            title="Simulate all tests passing"
          >
            <Zap size={14} />
            Demo
          </button>
          <button
            onclick={() => startDemo('mixed')}
            disabled={simulating}
            class="btn btn-sm flex items-center gap-1.5 text-warning"
            title="Simulate realistic mixed results"
          >
            <Zap size={14} />
            Mixed
          </button>
        </div>

        {#if isActive && auth.hasPermission('validation:manage')}
          <button
            onclick={() => { showTrigger = !showTrigger; }}
            class="btn btn-sm btn-primary flex items-center gap-1.5"
          >
            <Play size={14} />
            Trigger
          </button>
          <button
            onclick={cancelRun}
            disabled={cancelling}
            class="btn btn-sm btn-danger flex items-center gap-1.5"
          >
            <Ban size={14} />
            {cancelling ? 'Cancelling...' : 'Cancel'}
          </button>
        {/if}
      </div>
    </div>

    <!-- Trigger form -->
    {#if showTrigger}
      <div class="card mb-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-medium text-text-primary">Trigger K8s Validation Job</h3>
          <button onclick={() => { showTrigger = false; }} class="text-text-tertiary hover:text-text-primary text-xs">
            Cancel
          </button>
        </div>
        <form onsubmit={(e) => { e.preventDefault(); triggerRun(); }} class="flex items-end gap-3">
          <div class="flex-1">
            <label for="fw-version" class="mb-1 block text-2xs font-medium text-text-tertiary">Firmware Version</label>
            <input
              id="fw-version"
              bind:value={triggerFwVersion}
              placeholder="e.g. 0.1.12"
              required
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </div>
          <button type="submit" disabled={triggering || !triggerFwVersion.trim()} class="btn btn-sm btn-primary">
            {triggering ? 'Triggering...' : 'Trigger'}
          </button>
        </form>
      </div>
    {/if}

    <!-- Summary stats bar -->
    {#if liveTests.length > 0 || liveSummary}
      <div class="flex items-center gap-6 mb-4 px-4 py-3 rounded-lg bg-surface-1 border border-border">
        <!-- Progress -->
        <div class="flex items-center gap-2">
          {#if liveRunning}
            <Loader2 size={16} class="text-accent animate-spin" />
          {:else if liveSummary && liveSummary.failed > 0}
            <XCircle size={16} class="text-error" />
          {:else if liveSummary}
            <CheckCircle2 size={16} class="text-success" />
          {/if}
          <span class="text-sm font-medium text-text-primary">
            {#if liveRunning}
              Running...
            {:else if liveSummary && liveSummary.failed > 0}
              {liveSummary.failed} failed
            {:else if liveSummary}
              All tests passed
            {/if}
          </span>
        </div>

        <!-- Counts -->
        <div class="flex items-center gap-4 text-xs text-text-secondary">
          <span class="flex items-center gap-1">
            <CheckCircle2 size={12} class="text-success" />
            {livePassedCount} passed
          </span>
          <span class="flex items-center gap-1">
            <XCircle size={12} class="{liveFailedCount > 0 ? 'text-error' : 'text-text-tertiary'}" />
            {liveFailedCount} failed
          </span>
          <span class="flex items-center gap-1">
            <SkipForward size={12} class="text-text-tertiary" />
            {liveSkippedCount} skipped
          </span>
        </div>

        <!-- Duration -->
        <div class="ml-auto flex items-center gap-1 text-xs text-text-tertiary">
          <Clock size={12} />
          {#if liveSummary?.durationS}
            {formatDuration(liveSummary.durationS * 1000)}
          {:else if durationMs !== null}
            {formatDuration(durationMs)}
          {:else}
            —
          {/if}
        </div>
      </div>
    {/if}

    <!-- ═══ GITHUB ACTIONS STYLE: Two-column layout ═══ -->
    {#if liveTests.length > 0 || buildJobs.length > 0}
      <div class="flex gap-4" style="min-height: 500px;">
        <!-- Left sidebar: Stage list (Jobs in GH Actions) -->
        <div class="w-64 flex-shrink-0">
          <div class="sticky top-4 space-y-1">
            {#each stages as stage (stage.name)}
              {@const statusInfo = getStageStatusIcon(stage)}
              <button
                onclick={() => { selectedStage = stage.name; }}
                class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors
                  {selectedStage === stage.name
                    ? 'bg-accent-muted border border-accent/30 text-text-primary'
                    : 'hover:bg-surface-1 text-text-secondary'
                  }"
              >
                <svelte:component this={statusInfo.icon} size={16} class="{statusInfo.class}" />
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium truncate flex items-center gap-1.5">
                    {#if stage.type === 'build'}
                      <Package size={12} class="text-text-tertiary" />
                    {/if}
                    {stage.name}
                  </div>
                  <div class="text-2xs text-text-tertiary">
                    {#if stage.type === 'build'}
                      {stage.builds.length} build{stage.builds.length !== 1 ? 's' : ''}
                    {:else}
                      {stage.tests.length} test{stage.tests.length !== 1 ? 's' : ''}
                    {/if}
                    {#if stage.durationS > 0}
                      · {stage.durationS.toFixed(1)}s
                    {/if}
                  </div>
                </div>
                {#if stage.failed > 0}
                  <span class="text-2xs font-medium text-error bg-error-muted px-1.5 py-0.5 rounded">
                    {stage.failed}
                  </span>
                {/if}
              </button>
            {/each}

            <!-- Artifacts section in sidebar -->
            {#if artifacts.length > 0}
              <div class="mt-4 pt-4 border-t border-border">
                <div class="text-2xs font-medium text-text-tertiary uppercase tracking-wider mb-2 px-3">
                  Artifacts
                </div>
                {#each artifacts.slice(0, 5) as artifact (artifact.objectName)}
                  <a
                    href="/v2/validation/runs/{runId}/artifacts/{artifact.name}"
                    target="_blank"
                    class="flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-1 rounded transition-colors"
                  >
                    <Download size={12} class="text-text-tertiary" />
                    <span class="truncate">{artifact.name}</span>
                  </a>
                {/each}
                {#if artifacts.length > 5}
                  <div class="px-3 py-1 text-2xs text-text-tertiary">
                    +{artifacts.length - 5} more
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        </div>

        <!-- Right panel: Test list or build logs for selected stage -->
        <div class="flex-1 min-w-0">
          {#if selectedStageData}
            <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
              <!-- Stage header -->
              <div class="flex items-center gap-3 px-4 py-3 border-b border-border bg-surface-1">
                {#if selectedStageData.type === 'build'}
                  <Package size={16} class="text-text-tertiary" />
                {:else}
                  <Layers size={16} class="text-text-tertiary" />
                {/if}
                <span class="font-medium text-text-primary">{selectedStageData.name}</span>
                <span class="text-xs text-text-tertiary">
                  {#if selectedStageData.type === 'build'}
                    {selectedStageData.builds.length} build{selectedStageData.builds.length !== 1 ? 's' : ''}
                  {:else}
                    {selectedStageData.tests.length} test{selectedStageData.tests.length !== 1 ? 's' : ''}
                  {/if}
                </span>
                {#if selectedStageData.durationS > 0}
                  <span class="ml-auto text-xs text-text-tertiary flex items-center gap-1">
                    <Clock size={12} />
                    {selectedStageData.durationS.toFixed(1)}s
                  </span>
                {/if}
              </div>

              <!-- Build jobs list -->
              {#if selectedStageData.type === 'build'}
                <div class="divide-y divide-border">
                  {#each selectedStageData.builds as build (build.id)}
                    <div class="group">
                      <!-- Build row header -->
                      <button
                        onclick={() => { build.expanded = !build.expanded; buildJobs = buildJobs; }}
                        class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-1 transition-colors
                          {build.status === 'FAILED' ? 'bg-error-muted/30' : ''}
                          {build.status === 'BUILDING' ? 'bg-accent-muted/30' : ''}
                        "
                      >
                        <!-- Expand chevron -->
                        <div class="flex-shrink-0 text-text-tertiary">
                          {#if build.expanded}
                            <ChevronDown size={14} />
                          {:else}
                            <ChevronRight size={14} />
                          {/if}
                        </div>

                        <!-- Status icon -->
                        <div class="flex-shrink-0">
                          {#if build.status === 'QUEUED'}
                            <Circle size={14} class="text-text-tertiary" />
                          {:else if build.status === 'BUILDING'}
                            <Loader2 size={14} class="text-accent animate-spin" />
                          {:else if build.status === 'SUCCESS'}
                            <CheckCircle2 size={14} class="text-success" />
                          {:else if build.status === 'FAILED'}
                            <XCircle size={14} class="text-error" />
                          {:else if build.status === 'CANCELLED'}
                            <Ban size={14} class="text-text-tertiary" />
                          {/if}
                        </div>

                        <!-- Build info -->
                        <div class="flex-1 min-w-0">
                          <span class="text-sm font-mono text-text-primary">
                            {build.fwType}/{build.variant}
                          </span>
                          <span class="text-xs text-text-tertiary ml-2">
                            {build.branch}
                            {#if build.commitSha}
                              · {build.commitSha.slice(0, 7)}
                            {/if}
                          </span>
                        </div>

                        <!-- Duration -->
                        {#if build.durationSeconds !== null}
                          <span class="text-xs tabular-nums text-text-tertiary">
                            {build.durationSeconds}s
                          </span>
                        {/if}
                      </button>

                      <!-- Expanded build log panel -->
                      {#if build.expanded}
                        <div class="border-t border-border bg-[#0d1117]">
                          <!-- Error message -->
                          {#if build.errorMessage}
                            <div class="px-4 py-2 bg-error-muted/50 border-b border-error/20">
                              <pre class="text-xs text-error whitespace-pre-wrap font-mono leading-relaxed">{build.errorMessage}</pre>
                            </div>
                          {/if}

                          <!-- Build log output -->
                          {#if build.logOutput}
                            <div class="p-4 max-h-96 overflow-auto">
                              <pre class="text-xs text-[#c9d1d9] whitespace-pre-wrap font-mono leading-relaxed">{build.logOutput}</pre>
                            </div>
                          {:else if build.status === 'SUCCESS' || build.status === 'FAILED'}
                            <div class="px-4 py-3 text-xs text-text-tertiary italic">
                              No build log available.
                            </div>
                          {:else}
                            <div class="px-4 py-3 flex items-center gap-2 text-xs text-text-tertiary">
                              <Loader2 size={12} class="animate-spin" />
                              Build in progress...
                            </div>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              {:else}
                <!-- Test list -->
                <div class="divide-y divide-border">
                  {#each selectedStageData.tests as test (test.name)}
                    <div class="group">
                      <!-- Test row header -->
                      <button
                        onclick={() => toggleTestExpanded(test.name)}
                        class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-1 transition-colors
                          {test.status === 'failed' ? 'bg-error-muted/30' : ''}
                          {test.status === 'running' ? 'bg-accent-muted/30' : ''}
                          {test.status === 'skipped' ? 'opacity-60' : ''}
                        "
                      >
                        <!-- Expand chevron -->
                        <div class="flex-shrink-0 text-text-tertiary">
                          {#if test.expanded}
                            <ChevronDown size={14} />
                          {:else}
                            <ChevronRight size={14} />
                          {/if}
                        </div>

                        <!-- Status icon -->
                        <div class="flex-shrink-0">
                          {#if test.status === 'queued'}
                            <Circle size={14} class="text-text-tertiary" />
                          {:else if test.status === 'running'}
                            <Loader2 size={14} class="text-accent animate-spin" />
                          {:else if test.status === 'passed'}
                            <CheckCircle2 size={14} class="text-success" />
                          {:else if test.status === 'failed'}
                            <XCircle size={14} class="text-error" />
                          {:else if test.status === 'skipped'}
                            <SkipForward size={14} class="text-text-tertiary" />
                          {/if}
                        </div>

                        <!-- Test name -->
                        <span class="flex-1 text-sm font-mono text-text-primary truncate">
                          {test.name}
                        </span>

                        <!-- Duration -->
                        {#if test.durationS !== null}
                          <span class="text-xs tabular-nums text-text-tertiary">
                            {test.durationS.toFixed(2)}s
                          </span>
                        {/if}
                      </button>

                      <!-- Expanded log panel (GitHub Actions style) -->
                      {#if test.expanded}
                        <div class="border-t border-border bg-[#0d1117]">
                          <!-- Error message -->
                          {#if test.errorMessage}
                            <div class="px-4 py-2 bg-error-muted/50 border-b border-error/20">
                              <pre class="text-xs text-error whitespace-pre-wrap font-mono leading-relaxed">{test.errorMessage}</pre>
                            </div>
                          {/if}

                          <!-- Measurements -->
                          {#if test.measurements && Object.keys(test.measurements).length > 0}
                            <div class="px-4 py-2 border-b border-border/30">
                              <div class="flex flex-wrap gap-2">
                                {#each Object.entries(test.measurements) as [key, value]}
                                  <span class="inline-flex items-center gap-1 rounded bg-surface-2/50 px-2 py-1 text-2xs font-mono text-text-secondary">
                                    {key}: <span class="text-accent">{typeof value === 'number' ? value.toFixed(3) : value}</span>
                                  </span>
                                {/each}
                              </div>
                            </div>
                          {/if}

                          <!-- Log output (terminal style) -->
                          {#if test.logOutput}
                            <div class="p-4 max-h-96 overflow-auto">
                              <pre class="text-xs text-[#c9d1d9] whitespace-pre-wrap font-mono leading-relaxed">{test.logOutput}</pre>
                            </div>
                          {:else if test.status === 'skipped'}
                            <div class="px-4 py-3 text-xs text-text-tertiary">
                              Test was skipped (fixture/firmware mismatch or xfail).
                            </div>
                          {:else if test.status === 'passed' || test.status === 'failed'}
                            <div class="px-4 py-3 text-xs text-text-tertiary italic">
                              No log output captured for this test.
                            </div>
                          {:else}
                            <div class="px-4 py-3 flex items-center gap-2 text-xs text-text-tertiary">
                              <Loader2 size={12} class="animate-spin" />
                              Waiting for output...
                            </div>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {:else}
            <div class="flex items-center justify-center h-64 text-text-tertiary text-sm">
              Select a stage from the left to view details
            </div>
          {/if}
        </div>
      </div>
    {:else}
      <!-- No tests yet -->
      <div class="card text-center py-12">
        <Terminal size={48} class="mx-auto text-text-tertiary opacity-50 mb-4" />
        <div class="text-sm text-text-tertiary mb-4">
          No test executions yet.
        </div>
        <div class="flex justify-center gap-2">
          <button onclick={() => startDemo('happy')} disabled={simulating} class="btn btn-sm btn-primary">
            <Zap size={14} class="mr-1" />
            Start Demo
          </button>
        </div>
      </div>
    {/if}
  {/if}
</div>
