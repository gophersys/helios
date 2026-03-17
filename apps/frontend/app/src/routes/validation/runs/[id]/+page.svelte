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
  import { apiFetch, api, getToken } from '$lib/api';
  import type { ValidationRun, ValidationExecution } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { parseAnsi, stripAnsi } from '$lib/utils/ansi';
  import { highlightTraceback } from '$lib/utils/python-highlight';
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

  // Resizable split between test results and UART terminals
  let topPanelHeight = $state(45); // percentage of flex column wrapper
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
      if (stripAnsi(line).toLowerCase().includes(q)) acc.push(i);
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
    t: number;  // POSIX seconds
    mA: number; // current in milliamps
    mV: number; // voltage in millivolts
  }
  let powerSamples = $state<PowerSample[]>([]);      // DUT (ch0)
  let powerChgSamples = $state<PowerSample[]>([]);    // Charger (ch1)
  const POWER_WINDOW_S = 60; // show last 60 seconds

  // Derived search matches (reactive)
  const appMatches = $derived(getSearchMatches(uartAppLines, uartAppSearch));
  const commsMatches = $derived(getSearchMatches(uartCommsLines, uartCommsSearch));

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
      // Flush UART
      if (_uartAppPending.length > 0) {
        uartAppLines = [...uartAppLines, ..._uartAppPending].slice(-MAX_UART_LINES);
        _uartAppPending = [];
      }
      if (_uartCommsPending.length > 0) {
        uartCommsLines = [...uartCommsLines, ..._uartCommsPending].slice(-MAX_UART_LINES);
        _uartCommsPending = [];
      }
      // Flush log output
      if (_logChunkPending) {
        const runningTest = liveTests.find(t => t.status === 'running');
        if (runningTest) {
          runningTest.logOutput = (runningTest.logOutput || '') + _logChunkPending;
          liveTests = liveTests;
        }
        _logChunkPending = '';
      }
    }, 1000); // flush every 1s (perf: 500ms causes stutter during heavy FUOTA streaming)
  }

  // Auto-scroll UART terminals to bottom when new lines arrive
  $effect(() => {
    if (uartAppLines.length > 0 && !uartAppSearch) {
      const el = document.getElementById('uart-app-scroll');
      if (el) requestAnimationFrame(() => el.scrollTop = el.scrollHeight);
    }
  });
  $effect(() => {
    if (uartCommsLines.length > 0 && !uartCommsSearch) {
      const el = document.getElementById('uart-comms-scroll');
      if (el) requestAnimationFrame(() => el.scrollTop = el.scrollHeight);
    }
  });
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

      // Hydrate liveTests: merge config.testList (all tests) with executions (completed tests)
      // This ensures ALL tests show up even if only some have run
      const executions = (res.data as any).executions as any[] | undefined;
      const configTestList = (res.data as any).config?.testList as { name: string; module: string | null }[] | undefined;

      if (liveTests.length === 0) {
        // Build a map of execution results keyed by test name
        const execMap = new Map<string, any>();
        if (executions) {
          for (const ex of executions) {
            const name = ex.test?.name || 'Unknown';
            execMap.set(name, ex);
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
            if (!allTestNames.find(t => t.name === name)) {
              allTestNames.push({ name, module: ex.test?.category || null });
            }
          }
        }

        const hydratedTests: LiveTest[] = [];
        for (const t of allTestNames) {
          const ex = execMap.get(t.name);

          let status: LiveTest['status'] = 'queued';
          let logOutput: string | null = null;
          let errorMessage: string | null = null;
          let measurements: Record<string, unknown> | null = null;
          let durationS: number | null = null;

          if (ex) {
            if (ex.status === 'RUNNING') status = 'running';
            else if (ex.status === 'PASSED') status = 'passed';
            else if (ex.status === 'FAILED') status = 'failed';
            else if (ex.status === 'SKIPPED') status = 'skipped';

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
      const headers: Record<string, string> = {};
      const token = getToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`/v2/sessions/${runId}/artifacts/logs/output.log`, { headers });
      if (!res.ok) return;
      const text = await res.text();
      if (!text) return;

      // Find the start of the current test's output by looking for its name
      // The reporter prints "tests/fuota/test_file.py::TestClass::test_name" before each test
      const lines = text.split('\n');
      let startIdx = 0;

      // Search backwards for the test name marker
      for (let i = lines.length - 1; i >= 0; i--) {
        if (lines[i].includes(runningTest.name)) {
          startIdx = i + 1; // start AFTER the marker line
          break;
        }
      }

      // Take everything from the test start to the end
      const testOutput = lines.slice(startIdx).join('\n').trim();
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

  function toggleTestExpanded(testName: string): void {
    const test = liveTests.find(t => t.name === testName);
    if (test) test.expanded = !test.expanded;
  }

  function setupWebSocket(): void {
    if (!runId) return;
    unsubscribeWs = subscribeValidationRunWithLogs(
      runId,
      {
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

    <!-- ═══ RESIZABLE SPLIT: Test results (top) + UART terminals (bottom) ═══ -->
    {#if liveTests.length > 0 || buildJobs.length > 0}
    <div class="flex flex-col" data-resize-container style="height: calc(100vh - 90px);">
      <div class="flex gap-3 overflow-hidden" style="flex: 0 0 {topPanelHeight}%;">
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
                              Test was skipped.
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

        <!-- Power profiler panel (right side, hidden on narrow screens) -->
        <div class="flex-shrink-0 hidden xl:block self-start" style="width: 360px;">
          <div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col" style="height: 320px;">
            <div class="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-surface-1 flex-shrink-0">
              <Activity size={12} class="text-accent" />
              <span class="text-xs font-medium text-text-primary">Power</span>
              {#if powerSamples.length > 0}
                {@const last = powerSamples[powerSamples.length - 1]}
                {@const lastChg = powerChgSamples.length > 0 ? powerChgSamples[powerChgSamples.length - 1] : null}
                <span class="ml-auto text-2xs font-mono">
                  <span class="text-cyan-400">{last.mA.toFixed(1)}</span>
                  {#if lastChg}<span class="text-text-tertiary"> / </span><span class="text-orange-400">{lastChg.mA.toFixed(1)}</span>{/if}
                  <span class="text-text-tertiary"> mA</span>
                </span>
              {:else}
                <span class="ml-auto text-2xs text-text-tertiary">No data</span>
              {/if}
            </div>
            <div class="bg-[#0d1117] p-2 flex-1 overflow-hidden">
              {#if powerSamples.length > 1}
                {@const windowSamples = powerSamples.filter(s => s.t >= (powerSamples[powerSamples.length-1].t - POWER_WINDOW_S))}
                {@const allSamples = [...windowSamples, ...powerChgSamples.filter(s => s.t >= windowSamples[0].t)]}
                {@const minMA = 0}
                {@const maxMA = Math.max(120, ...allSamples.map(s => s.mA)) * 1.1}
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
                  <text x={pad.left + pw} y={h - 4} text-anchor="end" class="fill-text-tertiary" style="font-size: 7px;">-{(tMax - tMin).toFixed(0)}s</text>
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
                  <!-- Fill under DUT curve -->
                  <polygon
                    fill="rgba(34,211,238,0.08)"
                    points={`${pad.left},${pad.top + ph} ${windowSamples.map(s => {
                      const x = pad.left + ((s.t - tMin) / tRange) * pw;
                      const y = pad.top + ph - ((s.mA - minMA) / rangeMA) * ph;
                      return `${x},${y}`;
                    }).join(' ')} ${pad.left + pw},${pad.top + ph}`}
                  />
                  <!-- Charger line (orange) -->
                  {#if powerChgSamples.length > 1}
                    {@const chgWindow = powerChgSamples.filter(s => s.t >= tMin && s.t <= tMax)}
                    {#if chgWindow.length > 1}
                      <polyline
                        fill="none"
                        stroke="#fb923c"
                        stroke-width="1"
                        stroke-opacity="0.8"
                        points={chgWindow.map(s => {
                          const x = pad.left + ((s.t - tMin) / tRange) * pw;
                          const y = pad.top + ph - ((s.mA - minMA) / rangeMA) * ph;
                          return `${x},${y}`;
                        }).join(' ')}
                      />
                    {/if}
                  {/if}
                  <!-- Legend -->
                  <line x1={pad.left} y1={h - 12} x2={pad.left + 12} y2={h - 12} stroke="#22d3ee" stroke-width="1.5" />
                  <text x={pad.left + 15} y={h - 9} class="fill-text-tertiary" style="font-size: 6px;">DUT</text>
                  <line x1={pad.left + 35} y1={h - 12} x2={pad.left + 47} y2={h - 12} stroke="#fb923c" stroke-width="1" />
                  <text x={pad.left + 50} y={h - 9} class="fill-text-tertiary" style="font-size: 6px;">CHG</text>
                </svg>
              {:else}
                <div class="w-full h-full flex items-center justify-center" style="min-height: 250px;">
                  <div class="text-center">
                    <Activity size={24} class="mx-auto text-text-tertiary opacity-20 mb-2" />
                    <div class="text-xs text-text-tertiary">Waiting for power data</div>
                    <div class="text-2xs text-text-tertiary mt-1 opacity-60">Streams when DUT is powered</div>
                  </div>
                </div>
              {/if}
            </div>
          </div>
        </div>
      </div>

    <!-- Resize bar -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      onmousedown={startResize}
      class="h-3 my-1 flex items-center justify-center cursor-row-resize group rounded transition-colors
        {resizing ? 'bg-accent/20' : 'hover:bg-surface-2'}"
    >
      <div class="w-16 h-1 rounded-full transition-colors {resizing ? 'bg-accent' : 'bg-border group-hover:bg-text-tertiary'}"></div>
    </div>

    <!-- ═══ BOTTOM PANEL: Side-by-side UART Terminals ═══ -->
    <div class="flex-1 min-h-0 overflow-hidden">
      <!-- Wide screens: side-by-side terminals -->
      <div class="hidden md:grid md:grid-cols-2 gap-2 h-full" style="grid-template-columns: 1fr 1fr;">
        <!-- UART APP -->
        <div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col">
          <div class="flex items-center gap-2 px-3 py-1 border-b border-border bg-surface-1 flex-shrink-0">
            <Terminal size={12} class="text-green-400" />
            <span class="text-xs font-medium text-text-primary">nRF52840</span>
            {#if uartAppLines.length > 0}
              <span class="text-2xs text-text-tertiary ml-auto">{uartAppLines.length} lines</span>
            {/if}
          </div>
          <div class="flex items-center gap-1 px-2 py-0.5 border-b border-border bg-[#161b22]">
            <Search size={10} class="text-text-tertiary" />
            <input type="text" bind:value={uartAppSearch} placeholder="Search..." class="flex-1 bg-transparent text-xs text-[#c9d1d9] placeholder:text-text-tertiary outline-none font-mono" />
            {#if uartAppSearch && appMatches.length > 0}
              <span class="text-2xs text-text-tertiary">{(uartAppSearchIndex % appMatches.length) + 1}/{appMatches.length}</span>
              <button onclick={() => { uartAppSearchIndex = Math.max(0, uartAppSearchIndex - 1); scrollToMatch('uart-app-scroll', uartAppSearchIndex, appMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5 text-xs">&#x25B2;</button>
              <button onclick={() => { uartAppSearchIndex = uartAppSearchIndex + 1; scrollToMatch('uart-app-scroll', uartAppSearchIndex, appMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5 text-xs">&#x25BC;</button>
            {:else if uartAppSearch}
              <span class="text-2xs text-text-tertiary">0 results</span>
            {/if}
          </div>
          <div id="uart-app-scroll" class="flex-1 overflow-y-auto overflow-x-auto bg-[#0d1117] px-2 py-1 font-mono text-xs leading-snug">
            {#if uartAppLines.length > 0}
              {#each uartAppLines as line, i}
                <div data-line-index={i} class="whitespace-pre {appMatches.includes(i) ? 'bg-yellow-500/20' : ''}">{#each parseAnsi(line) as seg}<span class="{seg.classes || 'text-[#c9d1d9]'}">{seg.text}</span>{/each}</div>
              {/each}
            {:else}
              <div class="text-text-tertiary italic">Waiting for UART APP data...</div>
            {/if}
          </div>
        </div>

        <!-- UART COMMS -->
        <div class="rounded-lg border border-border bg-surface-0 overflow-hidden flex flex-col">
          <div class="flex items-center gap-2 px-3 py-1 border-b border-border bg-surface-1 flex-shrink-0">
            <Terminal size={12} class="text-blue-400" />
            <span class="text-xs font-medium text-text-primary">nRF9151</span>
            {#if uartCommsLines.length > 0}
              <span class="text-2xs text-text-tertiary ml-auto">{uartCommsLines.length} lines</span>
            {/if}
          </div>
          <div class="flex items-center gap-1 px-2 py-0.5 border-b border-border bg-[#161b22]">
            <Search size={10} class="text-text-tertiary" />
            <input type="text" bind:value={uartCommsSearch} placeholder="Search..." class="flex-1 bg-transparent text-xs text-[#c9d1d9] placeholder:text-text-tertiary outline-none font-mono" />
            {#if uartCommsSearch && commsMatches.length > 0}
              <span class="text-2xs text-text-tertiary">{(uartCommsSearchIndex % commsMatches.length) + 1}/{commsMatches.length}</span>
              <button onclick={() => { uartCommsSearchIndex = Math.max(0, uartCommsSearchIndex - 1); scrollToMatch('uart-comms-scroll', uartCommsSearchIndex, commsMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5 text-xs">&#x25B2;</button>
              <button onclick={() => { uartCommsSearchIndex = uartCommsSearchIndex + 1; scrollToMatch('uart-comms-scroll', uartCommsSearchIndex, commsMatches); }} class="text-text-tertiary hover:text-text-primary p-0.5 text-xs">&#x25BC;</button>
            {:else if uartCommsSearch}
              <span class="text-2xs text-text-tertiary">0 results</span>
            {/if}
          </div>
          <div id="uart-comms-scroll" class="flex-1 overflow-y-auto overflow-x-auto bg-[#0d1117] px-2 py-1 font-mono text-xs leading-snug">
            {#if uartCommsLines.length > 0}
              {#each uartCommsLines as line, i}
                <div data-line-index={i} class="whitespace-pre {commsMatches.includes(i) ? 'bg-yellow-500/20' : ''}">{#each parseAnsi(line) as seg}<span class="{seg.classes || 'text-[#c9d1d9]'}">{seg.text}</span>{/each}</div>
              {/each}
            {:else}
              <div class="text-text-tertiary italic">Waiting for UART COMMS data...</div>
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
    </div><!-- end flex column wrapper -->
    {/if}
  {/if}
</div>
