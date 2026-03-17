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
    Activity,
    PanelBottomClose,
    PanelBottomOpen,
    Search,
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
    subscribeValidationRunWithLogs,
    type ValidationTestStartEvent,
    type ValidationTestResultEvent,
    type ValidationRunFinishEvent,
    type ValidationLogChunkEvent,
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

  // Bottom panel: UART terminals + power profiler
  type BottomTab = 'uart_app' | 'uart_comms' | 'power';
  let bottomTab = $state<BottomTab>('uart_app');
  let uartAppLines = $state<string[]>([]);
  let uartCommsLines = $state<string[]>([]);
  let bottomPanelCollapsed = $state(false);

  // UART search
  let uartAppSearch = $state('');
  let uartCommsSearch = $state('');
  let uartAppSearchIndex = $state(0);
  let uartCommsSearchIndex = $state(0);

  // UART search match helpers
  function getSearchMatches(lines: string[], query: string): number[] {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return lines.reduce((acc: number[], line, i) => {
      if (line.toLowerCase().includes(q)) acc.push(i);
      return acc;
    }, []);
  }

  function scrollToMatch(containerId: string, matchIndex: number, matches: number[]) {
    if (matches.length === 0) return;
    const idx = matches[matchIndex % matches.length];
    const container = document.getElementById(containerId);
    if (!container) return;
    const lines = container.querySelectorAll('[data-line-index]');
    const target = lines[idx] as HTMLElement;
    if (target) {
      target.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }

  // Power profiler data
  interface PowerSample {
    t: number;  // seconds since start
    mA: number; // current in milliamps
    mV: number; // voltage in millivolts
  }
  let powerSamples = $state<PowerSample[]>([]);
  const POWER_WINDOW_S = 60; // show last 60 seconds

  // Derived search matches (reactive)
  const appMatches = $derived(getSearchMatches(uartAppLines, uartAppSearch));
  const commsMatches = $derived(getSearchMatches(uartCommsLines, uartCommsSearch));
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

    // Sort test stages by name so test_00_preflight is always first
    const sortedStages = Array.from(stageMap.values()).sort((a, b) => a.name.localeCompare(b.name));
    stageList.push(...sortedStages);
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
      const res = await apiFetch<ApiResponse<ValidationRun>>(`/v2/sessions/${runId}`);
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

          // Steps may come as 'steps' (new API) or 'results' (legacy)
          const steps = ex.steps || ex.results || [];
          if (steps.length) {
            const step = steps[0];
            // Step fields are at top level (not nested in 'result')
            logOutput = step.logOutput || (step.result && step.result.logOutput) || null;
            errorMessage = step.errorMessage || (step.result && step.result.errorMessage) || null;
            measurements = step.measurements || (step.result && step.result.measurements) || null;
            if (step.durationMs) {
              durationS = step.durationMs / 1000;
            }
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
        // Sort tests by name to maintain sequential order (test_01, test_02, ...)
        hydratedTests.sort((a, b) => a.name.localeCompare(b.name));
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
      await api.post(`/v2/sessions/${runId}/cancel`);
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
      await api.post(`/v2/sessions/${runId}/trigger`, {
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
      await api.post(`/v2/sessions/${runId}/demo/simulate?speed=0.1&scenario=${scenario}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to start demo';
      simulating = false;
    }
  }

  async function fetchArtifacts(): Promise<void> {
    artifactsLoading = true;
    try {
      const res = await apiFetch<ApiResponse<Artifact[]>>(`/v2/sessions/${runId}/artifacts`);
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
      const res = await fetch(`/v2/sessions/${runId}/artifacts/${artifact.name}`);
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

    <!-- Compact header bar: title + status + counts + duration in 1 row -->
    <div class="flex items-center gap-3 mb-3 px-4 py-2.5 rounded-lg bg-surface-1 border border-border">
      <!-- Title + status -->
      <h1 class="text-sm font-semibold text-text-primary truncate">{run.name}</h1>
      <StatusBadge status={run.status} />
      {#if liveRunning}
        <span class="inline-flex items-center gap-1 rounded-full bg-success-muted px-2 py-0.5 text-2xs font-medium text-success flex-shrink-0">
          <span class="relative flex h-1.5 w-1.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
            <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-success"></span>
          </span>
          LIVE
        </span>
      {/if}

      <!-- Separator -->
      <div class="w-px h-4 bg-border"></div>

      <!-- Metadata -->
      <div class="flex items-center gap-3 text-xs text-text-tertiary">
        {#if run.product}
          <span>{run.product.name}</span>
        {/if}
        {#if serialNumber}
          <span class="font-mono">{serialNumber}</span>
        {/if}
      </div>

      <!-- Spacer -->
      <div class="flex-1"></div>

      <!-- Test counts -->
      <div class="flex items-center gap-3 text-xs text-text-secondary flex-shrink-0">
        <span class="flex items-center gap-1">
          <CheckCircle2 size={12} class="text-success" />
          {livePassedCount}
        </span>
        <span class="flex items-center gap-1">
          <XCircle size={12} class="{liveFailedCount > 0 ? 'text-error' : 'text-text-tertiary'}" />
          {liveFailedCount}
        </span>
        <span class="flex items-center gap-1">
          <SkipForward size={12} class="text-text-tertiary" />
          {liveSkippedCount}
        </span>
      </div>

      <!-- Duration -->
      <div class="flex items-center gap-1 text-xs text-text-tertiary flex-shrink-0">
        <Clock size={12} />
        {#if liveSummary?.durationS}
          {formatDuration(liveSummary.durationS * 1000)}
        {:else if durationMs !== null}
          {formatDuration(durationMs)}
        {:else}
          —
        {/if}
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-1 flex-shrink-0">
        {#if isActive && auth.hasPermission('validation:manage')}
          <button onclick={cancelRun} disabled={cancelling} class="btn btn-xs btn-danger" title="Cancel run">
            <Ban size={12} />
          </button>
        {/if}
      </div>
    </div>

    <!-- ═══ GITHUB ACTIONS STYLE: Two-column layout ═══ -->
    {#if liveTests.length > 0 || buildJobs.length > 0}
      <div class="flex gap-3" style="min-height: 280px; height: calc(100vh - 340px);">
        <!-- Left sidebar: Stage list -->
        <div class="w-64 flex-shrink-0 overflow-y-auto">
          <div class="space-y-1">
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
                    href="/v2/sessions/{runId}/artifacts/{artifact.name}"
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

        <!-- Center panel: Test list or build logs for selected stage -->
        <div class="flex-1 min-w-0 overflow-y-auto">
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

        <!-- Power profiler panel (right side, hidden on narrow screens) -->
        <div class="w-72 flex-shrink-0 hidden xl:block">
          <div class="rounded-lg border border-border bg-surface-0 overflow-hidden h-full">
            <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1">
              <Activity size={12} class="text-accent" />
              <span class="text-xs font-medium text-text-primary">Power</span>
              {#if powerSamples.length > 0}
                {@const last = powerSamples[powerSamples.length - 1]}
                <span class="ml-auto text-2xs font-mono text-text-secondary">{last.mA.toFixed(1)} mA · {(last.mV / 1000).toFixed(2)} V</span>
              {:else}
                <span class="ml-auto text-2xs text-text-tertiary">No data</span>
              {/if}
            </div>
            <div class="bg-[#0d1117] p-2 flex-1 overflow-hidden">
              {#if powerSamples.length > 1}
                {@const windowSamples = powerSamples.filter(s => s.t >= (powerSamples[powerSamples.length-1].t - POWER_WINDOW_S))}
                {@const minMA = Math.max(0, Math.min(...windowSamples.map(s => s.mA)) - 5)}
                {@const maxMA = Math.max(...windowSamples.map(s => s.mA)) + 5}
                {@const rangeMA = Math.max(maxMA - minMA, 1)}
                {@const tMin = windowSamples[0].t}
                {@const tMax = windowSamples[windowSamples.length-1].t}
                {@const tRange = Math.max(tMax - tMin, 1)}
                {@const w = 240}
                {@const h = 200}
                {@const pad = { top: 8, right: 8, bottom: 20, left: 36 }}
                {@const pw = w - pad.left - pad.right}
                {@const ph = h - pad.top - pad.bottom}
                <svg viewBox="0 0 {w} {h}" class="w-full h-full">
                  <!-- Y axis labels -->
                  <text x={pad.left - 4} y={pad.top + 4} text-anchor="end" class="fill-text-tertiary" style="font-size: 8px;">{maxMA.toFixed(0)}</text>
                  <text x={pad.left - 4} y={pad.top + ph / 2 + 3} text-anchor="end" class="fill-text-tertiary" style="font-size: 8px;">{((maxMA + minMA) / 2).toFixed(0)}</text>
                  <text x={pad.left - 4} y={pad.top + ph + 3} text-anchor="end" class="fill-text-tertiary" style="font-size: 8px;">{minMA.toFixed(0)}</text>
                  <text x={4} y={pad.top + ph / 2} text-anchor="start" class="fill-text-tertiary" style="font-size: 7px;" transform="rotate(-90, 4, {pad.top + ph / 2})">mA</text>
                  <!-- X axis -->
                  <text x={pad.left} y={h - 4} class="fill-text-tertiary" style="font-size: 7px;">{tMin.toFixed(0)}s</text>
                  <text x={pad.left + pw} y={h - 4} text-anchor="end" class="fill-text-tertiary" style="font-size: 7px;">{tMax.toFixed(0)}s</text>
                  <!-- Grid lines -->
                  <line x1={pad.left} y1={pad.top} x2={pad.left + pw} y2={pad.top} stroke="#1e2a3a" stroke-width="0.5" />
                  <line x1={pad.left} y1={pad.top + ph / 2} x2={pad.left + pw} y2={pad.top + ph / 2} stroke="#1e2a3a" stroke-width="0.5" stroke-dasharray="2,2" />
                  <line x1={pad.left} y1={pad.top + ph} x2={pad.left + pw} y2={pad.top + ph} stroke="#1e2a3a" stroke-width="0.5" />
                  <!-- Data line -->
                  <polyline
                    fill="none"
                    stroke="#22d3ee"
                    stroke-width="1.5"
                    points={windowSamples.map(s => {
                      const x = pad.left + ((s.t - tMin) / tRange) * pw;
                      const y = pad.top + ph - ((s.mA - minMA) / rangeMA) * ph;
                      return `${x},${y}`;
                    }).join(' ')}
                  />
                  <!-- Fill under curve -->
                  <polygon
                    fill="rgba(34,211,238,0.08)"
                    points={`${pad.left},${pad.top + ph} ${windowSamples.map(s => {
                      const x = pad.left + ((s.t - tMin) / tRange) * pw;
                      const y = pad.top + ph - ((s.mA - minMA) / rangeMA) * ph;
                      return `${x},${y}`;
                    }).join(' ')} ${pad.left + pw},${pad.top + ph}`}
                  />
                </svg>
              {:else}
                <div class="h-full flex items-center justify-center">
                  <div class="text-center">
                    <Activity size={20} class="mx-auto text-text-tertiary opacity-20 mb-1" />
                    <div class="text-2xs text-text-tertiary">Waiting for power data</div>
                  </div>
                </div>
              {/if}
            </div>
          </div>
        </div>
      </div>
    {:else}
      <!-- No tests yet -->
      <div class="card text-center py-12">
        <Terminal size={48} class="mx-auto text-text-tertiary opacity-50 mb-4" />
        <div class="text-sm text-text-tertiary mb-4">
          No test executions yet.
        </div>
      </div>
    {/if}

    <!-- ═══ BOTTOM PANEL: Side-by-side UART Terminals ═══ -->
    <div class="mt-3" class:hidden={bottomPanelCollapsed}>
      <!-- Wide screens: side-by-side terminals -->
      <div class="hidden md:grid md:grid-cols-2 gap-3">
        <!-- UART APP -->
        <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
          <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1">
            <Terminal size={12} class="text-green-400" />
            <span class="text-xs font-medium text-text-primary">UART APP</span>
            <span class="text-2xs text-text-tertiary">nRF52840</span>
            {#if uartAppLines.length > 0}
              <span class="text-2xs text-text-tertiary ml-auto">{uartAppLines.length} lines</span>
            {/if}
          </div>
          <!-- Search bar -->
          <div class="flex items-center gap-1 px-2 py-1 border-b border-border bg-[#161b22]">
            <input
              type="text"
              bind:value={uartAppSearch}
              placeholder="Search..."
              class="flex-1 bg-transparent text-xs text-[#c9d1d9] placeholder:text-text-tertiary outline-none font-mono"
            />
            {#if uartAppSearch && appMatches.length > 0}
              <span class="text-2xs text-text-tertiary">{(uartAppSearchIndex % appMatches.length) + 1}/{appMatches.length}</span>
              <button onclick={() => { uartAppSearchIndex = Math.max(0, uartAppSearchIndex - 1); scrollToMatch('uart-app-scroll', uartAppSearchIndex, appMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5">&#x25B2;</button>
              <button onclick={() => { uartAppSearchIndex = uartAppSearchIndex + 1; scrollToMatch('uart-app-scroll', uartAppSearchIndex, appMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5">&#x25BC;</button>
            {:else if uartAppSearch}
              <span class="text-2xs text-text-tertiary">0 results</span>
            {/if}
          </div>
          <div id="uart-app-scroll" class="max-h-[36rem] overflow-y-auto bg-[#0d1117] p-2 font-mono text-xs leading-relaxed">
            {#if uartAppLines.length > 0}
              {#each uartAppLines as line, i}
                <div data-line-index={i} class="whitespace-pre {appMatches.includes(i) ? 'bg-yellow-500/20 text-yellow-200' : 'text-[#c9d1d9]'}">{line}</div>
              {/each}
            {:else}
              <div class="text-text-tertiary italic text-2xs">Waiting for UART APP data...</div>
            {/if}
          </div>
        </div>

        <!-- UART COMMS -->
        <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
          <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1">
            <Terminal size={12} class="text-blue-400" />
            <span class="text-xs font-medium text-text-primary">UART COMMS</span>
            <span class="text-2xs text-text-tertiary">nRF9151</span>
            {#if uartCommsLines.length > 0}
              <span class="text-2xs text-text-tertiary ml-auto">{uartCommsLines.length} lines</span>
            {/if}
          </div>
          <!-- Search bar -->
          <div class="flex items-center gap-1 px-2 py-1 border-b border-border bg-[#161b22]">
            <input
              type="text"
              bind:value={uartCommsSearch}
              placeholder="Search..."
              class="flex-1 bg-transparent text-xs text-[#c9d1d9] placeholder:text-text-tertiary outline-none font-mono"
            />
            {#if uartCommsSearch && commsMatches.length > 0}
              <span class="text-2xs text-text-tertiary">{(uartCommsSearchIndex % commsMatches.length) + 1}/{commsMatches.length}</span>
              <button onclick={() => { uartCommsSearchIndex = Math.max(0, uartCommsSearchIndex - 1); scrollToMatch('uart-comms-scroll', uartCommsSearchIndex, commsMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5">&#x25B2;</button>
              <button onclick={() => { uartCommsSearchIndex = uartCommsSearchIndex + 1; scrollToMatch('uart-comms-scroll', uartCommsSearchIndex, commsMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5">&#x25BC;</button>
            {:else if uartCommsSearch}
              <span class="text-2xs text-text-tertiary">0 results</span>
            {/if}
          </div>
          <div id="uart-comms-scroll" class="max-h-[36rem] overflow-y-auto bg-[#0d1117] p-2 font-mono text-xs leading-relaxed">
            {#if uartCommsLines.length > 0}
              {#each uartCommsLines as line, i}
                <div data-line-index={i} class="whitespace-pre {commsMatches.includes(i) ? 'bg-yellow-500/20 text-yellow-200' : 'text-[#c9d1d9]'}">{line}</div>
              {/each}
            {:else}
              <div class="text-text-tertiary italic text-2xs">Waiting for UART COMMS data...</div>
            {/if}
          </div>
        </div>
      </div>

      <!-- Narrow screens: tabbed fallback -->
      <div class="md:hidden rounded-lg border border-border bg-surface-0 overflow-hidden">
        <div class="flex items-center border-b border-border bg-surface-1 px-2">
          <button
            onclick={() => { bottomTab = 'uart_app'; }}
            class="flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors
              {bottomTab === 'uart_app' ? 'border-accent text-accent' : 'border-transparent text-text-tertiary hover:text-text-secondary'}"
          >
            <Terminal size={12} />
            APP
          </button>
          <button
            onclick={() => { bottomTab = 'uart_comms'; }}
            class="flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors
              {bottomTab === 'uart_comms' ? 'border-accent text-accent' : 'border-transparent text-text-tertiary hover:text-text-secondary'}"
          >
            <Terminal size={12} />
            COMMS
          </button>
        </div>
        <div class="max-h-[36rem] overflow-y-auto bg-[#0d1117] p-2 font-mono text-xs leading-relaxed">
          {#if bottomTab === 'uart_app'}
            {#if uartAppLines.length > 0}
              {#each uartAppLines as line}
                <div class="text-[#c9d1d9] whitespace-pre">{line}</div>
              {/each}
            {:else}
              <div class="text-text-tertiary italic text-2xs">Waiting for UART APP data...</div>
            {/if}
          {:else}
            {#if uartCommsLines.length > 0}
              {#each uartCommsLines as line}
                <div class="text-[#c9d1d9] whitespace-pre">{line}</div>
              {/each}
            {:else}
              <div class="text-text-tertiary italic text-2xs">Waiting for UART COMMS data...</div>
            {/if}
          {/if}
        </div>
      </div>
    </div>

    <!-- Collapse/expand toggle -->
    <button
      onclick={() => { bottomPanelCollapsed = !bottomPanelCollapsed; }}
      class="mt-1 w-full flex items-center justify-center gap-1 py-1 text-2xs text-text-tertiary hover:text-text-secondary transition-colors"
    >
      {#if bottomPanelCollapsed}
        <PanelBottomOpen size={12} />
        Show UART terminals
      {:else}
        <PanelBottomClose size={12} />
        Hide UART terminals
      {/if}
    </button>
  {/if}
</div>
