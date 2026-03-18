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
    Download,
    FileText,
    Loader2,
    Package,
    SkipForward,
    XCircle,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api, getToken } from '$lib/api';
  import type { ValidationRun, ValidationExecution } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { parseAnsi, stripAnsi } from '$lib/utils/ansi';
  import { highlightTraceback } from '$lib/utils/python-highlight';
  import UartTerminal from '$lib/components/validation/uart-terminal.svelte';
  import PowerChart from '$lib/components/validation/power-chart.svelte';
  import AccelChart from '$lib/components/validation/accel-chart.svelte';
  import type { PowerSample, AccelSample } from '$lib/components/validation/types';
  import {
    subscribeValidationRunWithLogs,
    type ValidationTestStartEvent,
    type ValidationTestResultEvent,
    type ValidationRunFinishEvent,
    type ValidationLogChunkEvent,
    type TelemetryEvent,
  } from '$lib/services/websocket';

  const auth = getAuth();
  const runId = $derived($page.params.id);

  // Svelte action: auto-scroll a container to bottom when content changes
  function autoScroll(node: HTMLElement, _trigger: unknown) {
    requestAnimationFrame(() => node.scrollTop = node.scrollHeight);
    return {
      update() {
        requestAnimationFrame(() => node.scrollTop = node.scrollHeight);
      }
    };
  }

  // Svelte action: removes max-w-7xl from the parent content wrapper
  // so this page can use the full viewport width for UART/power panels
  function fullWidth(node: HTMLElement) {
    const parent = node.closest('.max-w-7xl');
    if (parent) {
      parent.classList.remove('max-w-7xl');
      parent.classList.add('max-w-full');
    }
    return {
      destroy() {
        if (parent) {
          parent.classList.remove('max-w-full');
          parent.classList.add('max-w-7xl');
        }
      }
    };
  }

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
  // Auto-follow: automatically expand the running test and collapse the previous one.
  // Disabled when the user manually clicks a non-running test. Re-enabled when
  // the user clicks the currently-running test.
  let autoFollow = $state(true);
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
  // Mobile tabbed UART fallback now handled inside UartTerminal component
  let uartAppLines = $state<string[]>([]);
  let uartCommsLines = $state<string[]>([]);
  let bottomPanelCollapsed = $state(false);

  // Resizable split between test results and UART terminals
  let topPanelHeight = $state(50); // percentage of flex column wrapper
  let resizing = $state(false);
  let flexColumnEl: HTMLElement | null = null;

  function startResize(e: MouseEvent) {
    e.preventDefault();
    resizing = true;
    const startY = e.clientY;
    const startHeight = topPanelHeight;
    // Find the flex column wrapper (parent of the resize bar)
    const wrapper = (e.target as HTMLElement).closest('[data-resize-container]') as HTMLElement;
    if (!wrapper) return;
    const wrapperHeight = wrapper.getBoundingClientRect().height;

    function onMove(ev: MouseEvent) {
      const delta = ev.clientY - startY;
      const deltaPercent = (delta / wrapperHeight) * 100;
      topPanelHeight = Math.max(15, Math.min(80, startHeight + deltaPercent));
    }

    function onUp() {
      resizing = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }

    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // UART search state moved into UartTerminal component

  // Power profiler data (PowerSample type imported from components/validation/types)
  let powerSamples = $state<PowerSample[]>([]);
  let powerChgSamples = $state<PowerSample[]>([]);
  let accelSamples = $state<AccelSample[]>([]);
  const POWER_WINDOW_S = 60;

  // Derived search matches (reactive)
  // UART search matches now computed inside UartTerminal component

  // Performance: throttle UART + log updates to avoid excessive re-renders
  const MAX_UART_LINES = 1500; // keep last N lines per terminal (perf: 5000 causes lag during FUOTA)
  let _uartAppPending: string[] = [];
  let _uartCommsPending: string[] = [];
  let _logChunkPending = '';
  let _flushTimer: ReturnType<typeof setTimeout> | null = null;

  function _scheduleFlush() {
    if (_flushTimer) return;
    _flushTimer = setTimeout(() => {
      _flushTimer = null;
      let dirty = false;

      // Flush UART — only trigger reactivity if there are actual new lines
      if (_uartAppPending.length > 0) {
        uartAppLines = [...uartAppLines, ..._uartAppPending].slice(-MAX_UART_LINES);
        _uartAppPending = [];
      }
      if (_uartCommsPending.length > 0) {
        uartCommsLines = [...uartCommsLines, ..._uartCommsPending].slice(-MAX_UART_LINES);
        _uartCommsPending = [];
      }
      // Flush log output — only trigger liveTests reactivity if there's actual content
      if (_logChunkPending) {
        const runningTest = liveTests.find(t => t.status === 'running');
        if (runningTest) {
          runningTest.logOutput = (runningTest.logOutput || '') + _logChunkPending;
          dirty = true;
        }
        _logChunkPending = '';
      }
      // Only trigger expensive liveTests reactivity when log content changed
      if (dirty) {
        liveTests = liveTests;
      }
    }, 1000); // flush every 1s (perf: 500ms causes stutter during heavy FUOTA streaming)
  }

  // Auto-scroll moved into UartTerminal component
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

  const runConfig = $derived(run?.config as Record<string, unknown> | null);
  const serialNumber = $derived(
    (runConfig?.slot as Record<string, unknown> | null)?.dutSnr as string | undefined
    ?? runConfig?.serialNumber as string | undefined
  );
  const firmwareVariant = $derived(
    runConfig?.firmwareVariant as string | undefined
  );
  const imageTag = $derived(
    (runConfig?.trigger as Record<string, unknown> | null)?.imageTag as string | undefined
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

      // Hydrate liveTests: merge config.testList (all tests) with executions (completed tests)
      // This ensures ALL tests show up even if only some have run
      const executions = (res.data as any).executions as any[] | undefined;
      const configTestList = (res.data as any).config?.testList as { name: string; module: string | null }[] | undefined;

      if (liveTests.length === 0) {
        // Build a map of execution results keyed by "module::name" for unique matching
        // (test_01 and test_02 have identical test method names, only module differs)
        const execMap = new Map<string, any>();
        if (executions) {
          for (const ex of executions) {
            const name = ex.test?.name || 'Unknown';
            const module = ex.test?.category || '';
            execMap.set(`${module}::${name}`, ex);
          }
        }

        // Start from the full test list (all tests as queued)
        const allTestNames: { name: string; module: string | null }[] = [];
        if (configTestList?.length) {
          allTestNames.push(...configTestList);
        }
        // Add any executions not in the test list (edge case)
        if (executions) {
          for (const ex of executions) {
            const name = ex.test?.name || 'Unknown';
            const module = ex.test?.category || null;
            if (!allTestNames.find(t => t.name === name && t.module === module)) {
              allTestNames.push({ name, module });
            }
          }
        }

        const hydratedTests: LiveTest[] = [];
        for (const t of allTestNames) {
          const ex = execMap.get(`${t.module || ''}::${t.name}`);

          let status: LiveTest['status'] = 'queued';
          let logOutput: string | null = null;
          let errorMessage: string | null = null;
          let measurements: Record<string, unknown> | null = null;
          let durationS: number | null = null;

          if (ex) {
            if (ex.status === 'RUNNING') status = run?.status === 'ACTIVE' ? 'running' : 'skipped';
            else if (ex.status === 'PASSED') status = 'passed';
            else if (ex.status === 'FAILED') status = 'failed';
            else if (ex.status === 'SKIPPED' || ex.status === 'CANCELLED') status = 'skipped';

            const steps = ex.steps || ex.results || [];
            if (steps.length) {
              const step = steps[0];
              logOutput = step.logOutput || (step.result && step.result.logOutput) || null;
              errorMessage = step.errorMessage || (step.result && step.result.errorMessage) || null;
              measurements = step.measurements || (step.result && step.result.measurements) || null;
              if (step.durationMs) durationS = step.durationMs / 1000;
            }

            if (durationS === null && ex.startedAt && ex.finishedAt) {
              const start = new Date(ex.startedAt).getTime();
              const end = new Date(ex.finishedAt).getTime();
              durationS = (end - start) / 1000;
            }
          }

          hydratedTests.push({
            name: t.name,
            module: t.module,
            status,
            durationS,
            errorMessage,
            measurements,
            logOutput,
            expanded: status === 'failed',
          });
        }
        hydratedTests.sort((a, b) => a.name.localeCompare(b.name));
        liveTests = hydratedTests;

        // Check if run is finished
        if (res.data.status !== 'ACTIVE' && res.data.status !== 'PENDING') {
          liveFinished = true;
          liveRunning = false;
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
      // Update UI state immediately — don't wait for WebSocket
      liveRunning = false;
      liveFinished = true;
      for (const t of liveTests) {
        if (t.status === 'queued' || t.status === 'running') {
          t.status = 'skipped';
        }
      }
      liveTests = liveTests;
      await fetchRun();
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
      // Load telemetry from artifacts (for post-run viewing)
      loadTelemetryFromArtifacts(res.data);
      // Load historical test output for the currently running test
      loadRunningTestOutput(res.data);
    } catch {
      artifacts = [];
    } finally {
      artifactsLoading = false;
    }
  }

  async function loadRunningTestOutput(arts: Artifact[]): Promise<void> {
    // If a test is running but has no logOutput (page loaded mid-test),
    // fetch the output.log which contains all stdout, find the current
    // test's section, and populate it
    const runningTest = liveTests.find(t => t.status === 'running' && !t.logOutput);
    if (!runningTest) return;

    const outputLog = arts.find(a => a.name === 'logs/output.log');
    if (!outputLog) return;

    try {
      // Fetch via apiFetch (handles auth properly — JWT from cookie or token)
      let text: string;
      try {
        const headers: Record<string, string> = {};
        const token = getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch(`/v2/sessions/${runId}/artifacts/logs/output.log`, { headers });
        if (!res.ok) return;
        text = await res.text();
      } catch { return; }
      if (!text || text.startsWith('{')) return; // skip JSON error responses

      // Take last 500 lines of stdout as the running test's output
      const lines = text.split('\n');
      const testOutput = lines.slice(-500).join('\n').trim();
      if (testOutput) {
        runningTest.logOutput = testOutput;
        liveTests = liveTests;
      }
    } catch {
      // Ignore — log-chunk streaming will populate going forward
    }
  }

  async function loadTelemetryFromArtifacts(arts: Artifact[]): Promise<void> {
    // Find telemetry JSONL files (per-test-step)
    const telemetryArts = arts.filter(a => a.name.startsWith('telemetry/') && a.name.endsWith('.jsonl'));
    // Fallback: legacy UART log files
    const uartArts = arts.filter(a => a.name.endsWith('_uart.log'));

    const artList = telemetryArts.length > 0 ? telemetryArts : uartArts;
    if (artList.length === 0) return;

    const appLines: string[] = [];
    const commsLines: string[] = [];
    const power: typeof powerSamples = [];

    for (const art of artList) {
      try {
        // Fetch artifact content (proxied through API, not a redirect)
        const headers: Record<string, string> = {};
        const token = getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`/v2/sessions/${runId}/artifacts/${art.name}`, { headers });
        if (!res.ok) continue;
        const text = await res.text();

        if (!text) continue;

        if (art.name.endsWith('.jsonl')) {
          // Parse JSONL telemetry
          for (const line of text.split('\n')) {
            if (!line.trim()) continue;
            try {
              const s = JSON.parse(line);
              if (s.type === 'uart') {
                const ts = new Date(s.t * 1000).toISOString().slice(11, 23);
                const formatted = `\x1b[36m[${ts}]\x1b[0m ${s.line}`;
                if (s.target === 'app') appLines.push(formatted);
                else if (s.target === 'comms') commsLines.push(formatted);
              } else if (s.type === 'power') {
                power.push({ t: s.t, mA: s.mA, mV: s.mV });
              }
            } catch {
              // Skip malformed lines
            }
          }
        } else {
          // Legacy: raw UART log (both processors mixed)
          const header = `── ${art.name} ──`;
          const lines = text.split('\n').filter(l => l.length > 0);
          appLines.push(header, ...lines);
          commsLines.push(header, ...lines);
        }
      } catch {
        // Skip artifacts that can't be loaded
      }
    }

    // Cap lines to prevent browser lag (keep last MAX_UART_LINES)
    if (appLines.length > MAX_UART_LINES) {
      const truncated = appLines.length - MAX_UART_LINES;
      uartAppLines = [`--- ${truncated.toLocaleString()} earlier lines truncated ---`, ...appLines.slice(-MAX_UART_LINES)];
    } else if (appLines.length > 0) {
      uartAppLines = appLines;
    }
    if (commsLines.length > MAX_UART_LINES) {
      const truncated = commsLines.length - MAX_UART_LINES;
      uartCommsLines = [`--- ${truncated.toLocaleString()} earlier lines truncated ---`, ...commsLines.slice(-MAX_UART_LINES)];
    } else if (commsLines.length > 0) {
      uartCommsLines = commsLines;
    }
    // Power: keep last 2 min only
    if (power.length > 300) {
      const cutoff = power[power.length - 1].t - 120;
      powerSamples = power.filter(s => s.t > cutoff);
    } else if (power.length > 0) {
      powerSamples = power;
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

  function toggleTestExpanded(testName: string, module?: string | null): void {
    const test = module
      ? liveTests.find(t => t.name === testName && t.module === module)
      : liveTests.find(t => t.name === testName);
    if (!test) return;
    test.expanded = !test.expanded;

    // Auto-follow logic: if user clicks the running test, resume following.
    // If user clicks any other test, stop following.
    if (test.status === 'running') {
      autoFollow = test.expanded;
    } else {
      autoFollow = false;
    }
  }

  function setupWebSocket(): void {
    if (!runId) return;
    unsubscribeWs = subscribeValidationRunWithLogs(
      runId,
      {
        onTestStart: (data: ValidationTestStartEvent) => {
          liveRunning = true;
          const existing = liveTests.find(t => t.name === data.testName && t.module === data.module);
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
          // Auto-follow: expand the new running test, collapse the previous one
          if (autoFollow) {
            for (const t of liveTests) {
              t.expanded = (t.name === data.testName);
            }
            liveTests = liveTests;
          }
        },
        onTestResult: (data: ValidationTestResultEvent) => {
          const existing = liveTests.find(t => t.name === data.testName && t.module === data.module);
          if (existing) {
            existing.status = data.skipped ? 'skipped' : data.passed ? 'passed' : 'failed';
            existing.durationS = data.durationS;
            existing.errorMessage = data.errorMessage;
            existing.measurements = data.measurements;
            existing.logOutput = data.logOutput;
            // Auto-expand failures, auto-collapse passes (if following)
            if (!data.passed && !data.skipped) {
              existing.expanded = true;
            } else if (autoFollow) {
              existing.expanded = false;
            }
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
          // Reload artifacts to pick up UART logs written during the run
          fetchArtifacts();
        },
        onLogChunk: (data: ValidationLogChunkEvent) => {
          // Buffer log chunks and flush every 500ms (avoids per-chunk re-renders)
          try {
            const text = data.data ? atob(data.data) : (data.chunk || '');
            if (!text) return;
            _logChunkPending += text;
            _scheduleFlush();
          } catch {
            // Ignore decode errors
          }
        },
        onTestList: (data) => {
          // Pre-populate all test steps as 'queued' before they run
          if (liveTests.length === 0 || liveTests.every(t => t.status === 'queued')) {
            const tests: LiveTest[] = data.tests.map(t => ({
              name: t.name,
              module: t.module,
              status: 'queued' as const,
              durationS: null,
              errorMessage: null,
              measurements: null,
              logOutput: null,
              expanded: false,
            }));
            tests.sort((a, b) => a.name.localeCompare(b.name));
            liveTests = tests;
          }
        },
        onTelemetry: (data: TelemetryEvent) => {
          // Buffer UART samples and flush at 2Hz (500ms) for smooth performance.
          // Power samples update immediately (small data, chart needs real-time feel).
          let powerChanged = false;

          for (const s of data.samples) {
            if (s.type === 'uart') {
              const ts = new Date(s.t * 1000).toISOString().slice(11, 23);
              const formatted = `\x1b[36m[${ts}]\x1b[0m ${s.line}`;
              if (s.target === 'app') _uartAppPending.push(formatted);
              else if (s.target === 'comms') _uartCommsPending.push(formatted);
            } else if (s.type === 'power') {
              powerSamples.push({ t: s.t!, mA: s.mA!, mV: s.mV! });
              powerChanged = true;
            } else if (s.type === 'power_chg') {
              powerChgSamples.push({ t: s.t!, mA: s.mA!, mV: s.mV! });
              powerChanged = true;
            }
          }

          // Power: trim to last 60s and max 120 samples (avoid SVG lag)
          if (powerChanged) {
            const cutoff = (powerSamples.at(-1)?.t ?? 0) - 60;
            if (powerSamples.length > 120) powerSamples = powerSamples.filter(s => s.t > cutoff).slice(-120);
            if (powerChgSamples.length > 120) powerChgSamples = powerChgSamples.filter(s => s.t > cutoff).slice(-120);
            powerSamples = powerSamples;
            powerChgSamples = powerChgSamples;
          }

          // Schedule UART flush (batched at 500ms)
          if (_uartAppPending.length > 0 || _uartCommsPending.length > 0) _scheduleFlush();
        },
      },
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

<div class="animate-fade-in" use:fullWidth>
  {#if loading}
    <LoadingState message="Loading run..." />
  {:else if error && !run}
    <ErrorAlert message={error} />
  {:else if run}
    <ErrorAlert message={error} />

    <!-- Compact header bar: back + title + status + counts + duration in 1 row -->
    <div class="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-lg bg-surface-1 border border-border">
      <button onclick={() => goto('/validation/runs')} class="text-text-tertiary hover:text-text-primary transition-colors flex-shrink-0" title="Back to runs">
        <ArrowLeft size={14} />
      </button>
      <div class="w-px h-4 bg-border"></div>
      <h1 class="text-sm font-semibold text-text-primary truncate">{run.name}</h1>
      <StatusBadge status={run.status} />
      {#if liveRunning && run.status === 'ACTIVE'}
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
        {#if imageTag}
          <span class="font-mono text-2xs bg-surface-2 px-1.5 py-0.5 rounded" title="Validation image tag">{imageTag}</span>
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
        {#if isActive}
          <button onclick={cancelRun} disabled={cancelling} class="btn btn-xs flex items-center gap-1.5 text-error border-error/30 hover:bg-error/10" title="Cancel run">
            {#if cancelling}
              <Loader2 size={12} class="animate-spin" />
            {:else}
              <Ban size={12} />
            {/if}
            Cancel
          </button>
        {/if}
      </div>
    </div>

    <!-- ═══ MAIN LAYOUT: [Left: resizable tests+UART] [Right: fixed telemetry] ═══ -->
    {#if liveTests.length > 0 || buildJobs.length > 0}
    <div class="flex gap-3" style="height: calc(100vh - 90px);">
      <!-- Left side: resizable split between tests (top) and UART (bottom) -->
      <div class="flex-1 flex flex-col min-w-0" data-resize-container>
      <div class="flex gap-3 overflow-hidden" style="flex: 0 0 {topPanelHeight}%;">
        <!-- Left sidebar: Stage list -->
        <div class="w-56 flex-shrink-0 overflow-y-auto">
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
                      · {formatDuration(stage.durationS * 1000)}
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
                    {formatDuration(selectedStageData.durationS * 1000)}
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
                            {formatDuration((build.durationSeconds ?? 0) * 1000)}
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
                        onclick={() => toggleTestExpanded(test.name, test.module)}
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
                            {formatDuration((test.durationS ?? 0) * 1000)}
                          </span>
                        {/if}
                      </button>

                      <!-- Expanded log panel (GitHub Actions style) -->
                      {#if test.expanded}
                        <div class="border-t border-border bg-[#0d1117]">
                          <!-- Error traceback with Python syntax highlighting -->
                          {#if test.errorMessage}
                            {@const highlighted = highlightTraceback(test.errorMessage)}
                            {@const fileLine = highlighted.find(l => l.isFilePath)}
                            <div class="border-b border-error/20">
                              <!-- File badge -->
                              {#if fileLine}
                                <div class="px-4 py-1.5 bg-[#161b22] border-b border-border/30 flex items-center gap-2">
                                  <FileText size={12} class="text-text-tertiary" />
                                  <span class="text-xs font-mono text-accent">{fileLine.filePath}</span>
                                  {#if fileLine.fileLineNum}
                                    <span class="text-2xs font-mono text-orange-300">line {fileLine.fileLineNum}</span>
                                  {/if}
                                </div>
                              {/if}
                              <!-- Highlighted code -->
                              <div class="px-2 py-2 bg-[#0d1117] max-h-80 overflow-auto font-mono text-xs leading-relaxed">
                                {#each highlighted as line}
                                  <div class="flex {line.isMarker ? 'bg-warning/10 border-l-2 border-warning' : line.isError ? 'bg-error/5 border-l-2 border-error' : line.isFilePath ? 'hidden' : ''}">
                                    <span class="w-8 text-right pr-2 select-none flex-shrink-0" style="color: #4b5563">{line.lineNum || ''}</span>
                                    <span class="flex-1 whitespace-pre-wrap">{#each line.segments as seg}<span style={seg.cls}>{seg.text}</span>{/each}</span>
                                  </div>
                                {/each}
                              </div>
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
                            <div class="border-t border-border/20">
                              <div class="px-4 py-1 text-2xs font-medium text-text-tertiary bg-[#161b22]">Output</div>
                              <div class="px-4 py-2 max-h-96 overflow-auto bg-[#0d1117] font-mono text-xs leading-relaxed" use:autoScroll={test.logOutput}>
                                {#each test.logOutput.split('\n') as line}
                                  <div class="whitespace-pre-wrap">{#each parseAnsi(line) as seg}<span class="{seg.classes || 'text-[#c9d1d9]'}">{seg.text}</span>{/each}</div>
                                {/each}
                              </div>
                            </div>
                          {:else if test.status === 'skipped'}
                            <div class="px-4 py-3 text-xs text-text-tertiary">
                              {run?.status === 'CANCELLED' ? 'Run was cancelled.' : 'Test was skipped.'}
                            </div>
                          {:else if test.status === 'running'}
                            <div class="px-4 py-3 flex items-center gap-2 text-xs text-text-tertiary">
                              <Loader2 size={12} class="animate-spin" />
                              Waiting for output...
                            </div>
                          {:else if test.status === 'passed' || test.status === 'failed'}
                            <div class="px-4 py-3 text-xs text-text-tertiary italic">
                              No log output captured.
                            </div>
                          {:else}
                            <div class="px-4 py-3 text-xs text-text-tertiary italic">
                              Queued
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

      </div><!-- end top row (stages + test steps) -->

        <!-- Resize bar -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          onmousedown={startResize}
          class="h-3 my-1 flex items-center justify-center cursor-row-resize group rounded transition-colors
            {resizing ? 'bg-accent/20' : 'hover:bg-surface-2'}"
        >
          <div class="w-16 h-1 rounded-full transition-colors {resizing ? 'bg-accent' : 'bg-border group-hover:bg-text-tertiary'}"></div>
        </div>

        <!-- UART Terminals -->
        <div class="flex-1 min-h-0 overflow-hidden">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2 h-full">
            <UartTerminal lines={uartAppLines} label="nRF52840" iconColor="text-green-400" />
            <UartTerminal lines={uartCommsLines} label="nRF9151" iconColor="text-blue-400" />
          </div>
        </div>
      </div><!-- end left column (resizable) -->

      <!-- Right column: telemetry (fixed, independent of resize) -->
      <div class="w-80 flex-shrink-0 hidden xl:flex flex-col gap-2">
        <div class="flex-1 min-h-0">
          <PowerChart samples={powerSamples} chgSamples={powerChgSamples} windowSeconds={POWER_WINDOW_S} />
        </div>
        <div class="flex-1 min-h-0">
          <AccelChart samples={accelSamples} />
        </div>
      </div>
    </div><!-- end main layout row -->
    {/if}
  {/if}
</div>
