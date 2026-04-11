import { getContext, setContext } from 'svelte';
import { apiFetch, api, getToken } from '$lib/api';
import type { ValidationRun } from '$lib/types/models';
import type { ApiResponse } from '$lib/types';
import type { PowerSample, AccelSample, JoulescopeSample } from './types';
import type { TelemetryManifest, TimeRange, StepInfo } from './time-context';
import {
  subscribeRunWithLogs,
  type ValidationTestStartEvent,
  type ValidationTestResultEvent,
  type ValidationRunFinishEvent,
  type ValidationLogChunkEvent,
  type TelemetryEvent,
} from '$lib/services/websocket';
import { SlotContext } from '$lib/components/execution/slot-context.svelte';

// ── Shared interfaces ──────────────────────────────────────────────────

export interface LiveTest {
  name: string;
  module: string | null;
  status: 'queued' | 'running' | 'passed' | 'failed' | 'skipped';
  durationS: number | null;
  startedAtMs: number | null;
  errorMessage: string | null;
  measurements: Record<string, unknown> | null;
  logOutput: string | null;
  expanded: boolean;
  [key: string]: unknown;
}

export interface Artifact {
  name: string;
  objectName: string;
  size: number;
  lastModified: string | null;
  contentType: string | null;
}

export interface BuildJob {
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

export interface TimestampedLine {
  t: number;
  line: string;
}

export interface Stage {
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

// ── RunContext class ───────────────────────────────────────────────────

const MAX_UART_LINES = 1500;

class RunContext {
  // Core run state
  run = $state<ValidationRun | null>(null);
  loading = $state(true);
  error = $state<string | null>(null);

  // Cancel state
  cancelling = $state(false);
  confirmCancel = $state(false);
  cancelConfirmText = $state('');

  // Trigger state
  triggering = $state(false);
  showTrigger = $state(false);
  triggerFwVersion = $state('');

  // Simulation
  simulating = $state(false);

  // Live test timeline state (from WebSocket)
  liveTests = $state<LiveTest[]>([]);
  liveRunning = $state(false);
  liveFinished = $state(false);
  liveSummary = $state<{
    total: number;
    passed: number;
    failed: number;
    errors: number;
    durationS: number | null;
  } | null>(null);

  // Live clock for running timers
  nowMs = $state(Date.now());

  // Auto-follow: expand running test, collapse previous
  autoFollow = $state(true);

  // Stage selection
  selectedStage = $state<string | null>(null);

  // Artifacts
  artifacts = $state<Artifact[]>([]);
  artifactsLoading = $state(false);

  // UART lines
  uartAppLines = $state<string[]>([]);
  uartCommsLines = $state<string[]>([]);

  // Bottom panel
  bottomPanelCollapsed = $state(false);

  // Resizable layout state
  topPanelHeight = $state(50);
  resizing = $state(false);
  sidebarWidth = $state(192);
  chartsWidth = $state(576);
  vResizing = $state<'sidebar' | 'charts' | null>(null);

  // Power / accel profiler data
  powerSamples = $state<PowerSample[]>([]);
  powerChgSamples = $state<PowerSample[]>([]);
  powerJsSamples = $state<JoulescopeSample[]>([]);
  accelSamples = $state<AccelSample[]>([]);
  readonly POWER_WINDOW_S = 60;

  // Post-analysis telemetry state
  telemetryManifest = $state<TelemetryManifest | null>(null);
  selectedRange = $state<TimeRange | null>(null);
  historicalPower = $state<PowerSample[]>([]);
  historicalPowerChg = $state<PowerSample[]>([]);
  historicalPowerJs = $state<JoulescopeSample[]>([]);
  historicalUartAppTs = $state<TimestampedLine[]>([]);
  historicalUartCommsTs = $state<TimestampedLine[]>([]);
  telemetryLoading = $state(false);

  // Build jobs from pipeline
  buildJobs = $state<BuildJob[]>([]);

  // Log viewer state
  logContent = $state<string | null>(null);
  logArtifactName = $state<string | null>(null);

  // Internal buffering / throttling
  private _uartAppPending: string[] = [];
  private _uartCommsPending: string[] = [];
  private _logChunkPending = '';
  private _flushTimer: ReturnType<typeof setTimeout> | null = null;

  // Lifecycle handles
  private _pollInterval: ReturnType<typeof setInterval> | null = null;
  private _clockInterval: ReturnType<typeof setInterval> | null = null;
  private _unsubscribeWs: (() => void) | null = null;
  private _initialFocusDone = false;
  private _telemetryFetched = false;
  private _runId: string;

  // ── Derived values ────────────────────────────────────────────────

  readonly historicalUartApp = $derived(this.historicalUartAppTs.map(l => l.line));
  readonly historicalUartComms = $derived(this.historicalUartCommsTs.map(l => l.line));
  readonly analysisMode = $derived(this.run?.status !== 'ACTIVE' && this.telemetryManifest !== null);
  readonly isActive = $derived(this.run?.status === 'ACTIVE');

  // Live manifest: built from liveTests so the timeline widget works during active runs.
  // Returns a manifest even when no tests have started yet (all queued) so the
  // timeline shows a single growing "in progress" segment.
  readonly liveManifest = $derived.by((): TelemetryManifest | null => {
    if (!this.run?.startedAt) return null;
    const steps: StepInfo[] = [];
    const runStartS = new Date(this.run.startedAt).getTime() / 1000;
    for (const t of this.liveTests) {
      if (t.status === 'queued') continue;
      const startS = t.startedAtMs ? t.startedAtMs / 1000 : runStartS;
      let endS: number;
      if (t.durationS !== null && t.durationS > 0) {
        endS = startS + t.durationS;
      } else if (t.status === 'running') {
        endS = this.nowMs / 1000; // grows with live clock
      } else {
        endS = startS + 0.5; // minimal width for skipped/unknown
      }
      steps.push({ name: t.name, module: t.module, startedAt: startS, finishedAt: endS, status: t.status });
    }
    // When no tests have started yet, show a single growing "in progress" segment
    // so the timeline is visible from the moment the run starts.
    if (steps.length === 0) {
      steps.push({
        name: 'Initializing',
        module: null,
        startedAt: runStartS,
        finishedAt: this.nowMs / 1000,
        status: 'running',
      });
    }
    return {
      version: 1,
      runId: this._runId,
      startedAt: runStartS,
      finishedAt: this.nowMs / 1000,
      totalSamples: 0,
      channels: {},
      steps,
    };
  });

  // Active manifest: use telemetry manifest (post-analysis) or live manifest (active run)
  readonly activeManifest = $derived(this.telemetryManifest ?? this.liveManifest);

  readonly filteredPower = $derived.by(() => {
    if (!this.selectedRange) return this.historicalPower;
    return this.historicalPower.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
  });

  readonly filteredPowerChg = $derived.by(() => {
    if (!this.selectedRange) return this.historicalPowerChg;
    return this.historicalPowerChg.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
  });

  readonly filteredPowerJs = $derived.by(() => {
    if (!this.selectedRange) return this.historicalPowerJs;
    return this.historicalPowerJs.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
  });

  readonly filteredUartApp = $derived.by(() => {
    if (!this.selectedRange || this.historicalUartAppTs.length === 0) return this.historicalUartApp;
    return this.historicalUartAppTs
      .filter(l => l.t >= this.selectedRange!.start && l.t <= this.selectedRange!.end)
      .map(l => l.line);
  });

  readonly filteredUartComms = $derived.by(() => {
    if (!this.selectedRange || this.historicalUartCommsTs.length === 0) return this.historicalUartComms;
    return this.historicalUartCommsTs
      .filter(l => l.t >= this.selectedRange!.start && l.t <= this.selectedRange!.end)
      .map(l => l.line);
  });

  // Filter data in BOTH analysis and live mode when a time range is selected.
  // In analysis mode, use historical data as the source; in live mode, filter
  // the live power samples so clicking a test step narrows the chart.
  readonly effectivePower = $derived.by(() => {
    if (this.analysisMode) return this.filteredPower;
    if (this.selectedRange) return this.powerSamples.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
    return this.powerSamples;
  });
  readonly effectivePowerChg = $derived.by(() => {
    if (this.analysisMode) return this.filteredPowerChg;
    if (this.selectedRange) return this.powerChgSamples.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
    return this.powerChgSamples;
  });
  readonly effectivePowerJs = $derived.by(() => {
    if (this.analysisMode) return this.filteredPowerJs;
    if (this.selectedRange) return this.powerJsSamples.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
    return this.powerJsSamples;
  });
  readonly effectiveUartApp = $derived.by(() => {
    if (this.analysisMode) return this.filteredUartApp.length > 0 ? this.filteredUartApp : this.uartAppLines;
    // In live mode with a selectedRange, keep showing live UART (no timestamps to filter on)
    return this.uartAppLines;
  });
  readonly effectiveUartComms = $derived.by(() => {
    if (this.analysisMode) return this.filteredUartComms.length > 0 ? this.filteredUartComms : this.uartCommsLines;
    return this.uartCommsLines;
  });

  readonly progressPct = $derived.by(() => {
    if (!this.run || !this.run.targetCount) return 0;
    return Math.round((this.run.completedCount / this.run.targetCount) * 100);
  });

  readonly durationMs = $derived.by(() => {
    if (!this.run?.startedAt) return null;
    const start = new Date(this.run.startedAt).getTime();
    const end = this.run.completedAt ? new Date(this.run.completedAt).getTime() : Date.now();
    return end - start;
  });

  readonly runConfig = $derived(this.run?.config as Record<string, unknown> | null);

  readonly serialNumber = $derived(
    (this.runConfig?.slot as Record<string, unknown> | null)?.dutSnr as string | undefined
    ?? this.runConfig?.serialNumber as string | undefined
  );

  readonly firmwareVariant = $derived(
    this.runConfig?.firmwareVariant as string | undefined
  );

  readonly imageTag = $derived(
    (this.runConfig?.trigger as Record<string, unknown> | null)?.imageTag as string | undefined
  );

  readonly stages = $derived.by(() => {
    const stageList: Stage[] = [];

    // Add Build stage if there are build jobs
    if (this.buildJobs.length > 0) {
      let passed = 0, failed = 0, running = 0, durationS = 0;
      for (const b of this.buildJobs) {
        if (b.status === 'SUCCESS') passed++;
        else if (b.status === 'FAILED') failed++;
        else if (b.status === 'BUILDING') running++;
        if (b.durationSeconds) durationS += b.durationSeconds;
      }
      stageList.push({
        name: 'Build',
        type: 'build',
        tests: [],
        builds: this.buildJobs,
        passed,
        failed,
        skipped: 0,
        running,
        durationS,
      });
    }

    // Add test stages
    const stageMap = new Map<string, Stage>();

    for (const test of this.liveTests) {
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

    const sortedStages = Array.from(stageMap.values()).sort((a, b) => a.name.localeCompare(b.name));
    stageList.push(...sortedStages);
    return stageList;
  });

  readonly selectedStageData = $derived(
    this.stages.find(s => s.name === this.selectedStage) || null
  );

  readonly livePassedCount = $derived(this.liveTests.filter(t => t.status === 'passed').length);
  readonly liveFailedCount = $derived(this.liveTests.filter(t => t.status === 'failed').length);
  readonly liveSkippedCount = $derived(this.liveTests.filter(t => t.status === 'skipped').length);
  readonly liveCompletedCount = $derived(this.livePassedCount + this.liveFailedCount + this.liveSkippedCount);

  // ── Shared SlotContext (for SlotExecutionView integration) ─────────

  /** Per-slot context that mirrors the run's primary slot state.
   *  Created lazily when the validation page needs SlotExecutionView. */
  slotCtx = $state<SlotContext | null>(null);

  /** SOC labels from boardRevision (for dynamic UART terminal labels). */
  socLabels = $state<string[]>([]);

  /** Create or return the SlotContext for the primary target. */
  getOrCreateSlotCtx(): SlotContext {
    if (!this.slotCtx) {
      this.slotCtx = new SlotContext(
        this.run?.targets?.[0]?.id || 'slot-0',
        0,
        this.serialNumber || '',
      );
      this.slotCtx.startClock();
    }
    return this.slotCtx;
  }

  /** Sync RunContext state → SlotContext (called after hydration). */
  syncToSlotCtx(): void {
    const slot = this.getOrCreateSlotCtx();

    // Map LiveTest[] → SlotLiveTest[]
    slot.liveTests = this.liveTests.map(t => ({
      name: t.name,
      module: t.module,
      status: t.status,
      durationS: t.durationS,
      startedAtMs: t.startedAtMs,
      errorMessage: t.errorMessage,
      measurements: t.measurements,
      logOutput: t.logOutput,
      expanded: t.expanded,
      steps: [],
    }));

    slot.liveRunning = this.liveRunning;
    slot.liveFinished = this.liveFinished;
    slot.hydrated = true;

    // Telemetry
    slot.powerSamples = this.powerSamples;
    slot.powerChgSamples = this.powerChgSamples;
    slot.powerJsSamples = this.powerJsSamples;
    slot.accelSamples = this.accelSamples;
    slot.uartAppLines = this.uartAppLines;
    slot.uartCommsLines = this.uartCommsLines;

    // Post-analysis
    slot.telemetryManifest = this.telemetryManifest;
    slot.historicalPower = this.historicalPower;
    slot.historicalPowerChg = this.historicalPowerChg;
    slot.historicalPowerJs = this.historicalPowerJs;

    // UI state sync (bidirectional — SlotContext is the source for layout)
    slot.selectedStage = this.selectedStage;
    slot.selectedRange = this.selectedRange;
    slot.autoFollow = this.autoFollow;

    // SOC labels from boardRevision
    if (this.run?.boardRevision?.socs) {
      this.socLabels = this.run.boardRevision.socs;
    }

    // Status
    if (this.run?.targets?.[0]) {
      slot.status = this.run.targets[0].status || 'PENDING';
      slot.serialNumber = this.run.targets[0].serialNumber || '';
    }
  }

  // ── Constructor ───────────────────────────────────────────────────

  constructor(runId: string) {
    this._runId = runId;
  }

  get runId(): string {
    return this._runId;
  }

  set runId(value: string) {
    this._runId = value;
  }

  // ── UART buffering / flush ────────────────────────────────────────

  private _scheduleFlush(): void {
    if (this._flushTimer) return;
    this._flushTimer = setTimeout(() => {
      this._flushTimer = null;
      let dirty = false;

      if (this._uartAppPending.length > 0) {
        this.uartAppLines = [...this.uartAppLines, ...this._uartAppPending].slice(-MAX_UART_LINES);
        this._uartAppPending = [];
      }
      if (this._uartCommsPending.length > 0) {
        this.uartCommsLines = [...this.uartCommsLines, ...this._uartCommsPending].slice(-MAX_UART_LINES);
        this._uartCommsPending = [];
      }
      if (this._logChunkPending) {
        const runningTest = this.liveTests.find(t => t.status === 'running');
        if (runningTest) {
          runningTest.logOutput = (runningTest.logOutput || '') + this._logChunkPending;
          dirty = true;
        }
        this._logChunkPending = '';
      }
      if (dirty) {
        this.liveTests = this.liveTests;
      }
    }, 200);
  }

  // ── Helper: find test ─────────────────────────────────────────────

  findTest(name: string, module?: string | null): LiveTest | undefined {
    if (module) {
      return this.liveTests.find(t => t.name === name && t.module === module);
    }
    return this.liveTests.find(t => t.name === name);
  }

  // ── Toggle test expanded ──────────────────────────────────────────

  toggleTestExpanded(testName: string, module?: string | null): void {
    const test = module
      ? this.liveTests.find(t => t.name === testName && t.module === module)
      : this.liveTests.find(t => t.name === testName);
    if (!test) return;
    test.expanded = !test.expanded;

    if (this.analysisMode && this.telemetryManifest && test.expanded) {
      const step = this.telemetryManifest.steps.find(s => s.name === testName && s.module === module);
      if (step) {
        this.selectedRange = { start: step.startedAt, end: step.finishedAt };
      }
    } else if (this.analysisMode && !test.expanded) {
      this.selectedRange = null;
    }

    if (test.status === 'running') {
      this.autoFollow = test.expanded;
    } else {
      this.autoFollow = false;
    }
  }

  // ── Data fetching methods ─────────────────────────────────────────

  async fetchRun(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<ValidationRun>>(`/v2/runs/${this._runId}`);
      this.run = res.data;
      this.error = null;

      // Hydrate build jobs from pipeline if present. The backend response shape
      // includes extra fields not in the generated ValidationRun type.
      type StepRecord = {
        logOutput?: string | null;
        errorMessage?: string | null;
        measurements?: Record<string, unknown> | null;
        durationMs?: number;
        result?: {
          logOutput?: string | null;
          errorMessage?: string | null;
          measurements?: Record<string, unknown> | null;
        };
      };
      type ExecutionRecord = {
        test?: { name?: string; category?: string };
        status?: string;
        steps?: StepRecord[];
        results?: StepRecord[];
        startedAt?: string;
        finishedAt?: string;
      };
      type RunExtras = {
        buildRun?: { builds?: Partial<BuildJob>[] };
        executions?: ExecutionRecord[];
        config?: { testList?: { name: string; module: string | null }[] };
      };
      const extras = res.data as ValidationRun & RunExtras;

      const buildRun = extras.buildRun;
      if (buildRun?.builds?.length) {
        this.buildJobs = buildRun.builds.map((b) => ({
          id: b.id ?? '',
          product: b.product ?? '',
          fwType: b.fwType ?? '',
          variant: b.variant ?? '',
          status: b.status ?? '',
          commitSha: b.commitSha ?? null,
          branch: b.branch ?? '',
          logOutput: b.logOutput ?? null,
          errorMessage: b.errorMessage ?? null,
          durationSeconds: b.durationSeconds ?? null,
          expanded: false,
        }));
      }

      // Hydrate liveTests
      const executions = extras.executions;
      const configTestList = extras.config?.testList;

      if (this.liveTests.length === 0 || this.liveTests.every(t => t.status === 'queued')) {
        const execMap = new Map<string, ExecutionRecord>();
        if (executions) {
          for (const ex of executions) {
            const name = ex.test?.name || 'Unknown';
            const module = ex.test?.category || '';
            execMap.set(`${module}::${name}`, ex);
          }
        }

        const allTestNames: { name: string; module: string | null }[] = [];
        if (configTestList?.length) {
          allTestNames.push(...configTestList);
        }
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
          const key = `${t.module || ''}::${t.name}`;
          const ex = execMap.get(key);

          let status: LiveTest['status'] = 'queued';
          let logOutput: string | null = null;
          let errorMessage: string | null = null;
          let measurements: Record<string, unknown> | null = null;
          let durationS: number | null = null;

          if (ex) {
            if (ex.status === 'RUNNING') {
              const moduleHasFailure = hydratedTests.some(
                h => h.module === t.module && h.status === 'failed'
              );
              status = (this.run?.status === 'ACTIVE' && !moduleHasFailure) ? 'running' : 'skipped';
            }
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
            startedAtMs: ex?.startedAt ? new Date(ex.startedAt).getTime() : null,
            errorMessage,
            measurements,
            logOutput,
            expanded: status === 'failed',
          });
        }
        hydratedTests.sort((a, b) => a.name.localeCompare(b.name));
        this.liveTests = hydratedTests;

        if ((res.data.status as string) !== 'ACTIVE' && (res.data.status as string) !== 'PENDING') {
          this.liveFinished = true;
          this.liveRunning = false;
        }

        // Auto-focus: expand the running test and select its stage on page load/reload
        const runningTest = this.liveTests.find(t => t.status === 'running');
        if (runningTest) {
          this.liveRunning = true;
          this.autoFollow = true;
          for (const t of this.liveTests) {
            t.expanded = (t === runningTest);
          }
          this.liveTests = this.liveTests;
          if (runningTest.module) {
            this.selectedStage = runningTest.module;
          }
          setTimeout(() => {
            const el = document.querySelector(`[data-test-name="${runningTest.name}"][data-test-module="${runningTest.module}"]`);
            if (el) {
              const panel = el.closest('.overflow-y-auto');
              if (panel) {
                const panelRect = panel.getBoundingClientRect();
                const elRect = el.getBoundingClientRect();
                panel.scrollTop += elRect.top - panelRect.top;
              }
            }
          }, 500);
        }

        // Backfill data for active runs
        if (res.data.status === 'ACTIVE') {
          const authHeaders = { 'Authorization': `Bearer ${getToken()}` };

          try {
            const logRes = await fetch(`/v2/runs/${this._runId}/artifacts/logs/output.log`, { headers: authHeaders });
            if (logRes.ok) {
              const fullLog = await logRes.text();
              const runningTest2 = this.liveTests.find(t => t.status === 'running');
              if (runningTest2 && fullLog) {
                runningTest2.logOutput = fullLog.slice(-10000);
                this.liveTests = this.liveTests;
              }
            }
          } catch { /* non-critical */ }

          try {
            const artRes = await fetch(`/v2/runs/${this._runId}/artifacts`, { headers: authHeaders });
            if (artRes.ok) {
              const artData = await artRes.json();
              const jsonlFiles = ((artData.data || []) as { name?: string }[]).filter((a) => a.name?.startsWith('telemetry/') && a.name?.endsWith('.jsonl'));
              for (const art of jsonlFiles) {
                try {
                  const jRes = await fetch(`/v2/runs/${this._runId}/artifacts/${art.name}`, { headers: authHeaders });
                  if (!jRes.ok) continue;
                  const text = await jRes.text();
                  for (const line of text.split('\n')) {
                    if (!line.trim()) continue;
                    try {
                      const s = JSON.parse(line);
                      if (s.type === 'power' && s.mA !== undefined) {
                        this.powerSamples.push({ t: s.t, mA: s.mA, mV: s.mV });
                      } else if (s.type === 'power_chg' && s.mA !== undefined) {
                        this.powerChgSamples.push({ t: s.t, mA: s.mA, mV: s.mV });
                      }
                    } catch { /* skip */ }
                  }
                } catch { /* skip */ }
              }
              if (this.powerSamples.length > 0) this.powerSamples = [...this.powerSamples];
              if (this.powerChgSamples.length > 0) this.powerChgSamples = [...this.powerChgSamples];
            }
          } catch { /* non-critical */ }
        }
      }
      // Sync to shared SlotContext
      this.syncToSlotCtx();
    } catch (err: unknown) {
      this.error = err instanceof Error ? err.message : 'Failed to load run';
    } finally {
      this.loading = false;
    }
  }

  async cancelRun(): Promise<void> {
    this.cancelling = true;
    try {
      await api.post(`/v2/runs/${this._runId}/cancel`);
      this.liveRunning = false;
      this.liveFinished = true;
      for (const t of this.liveTests) {
        if (t.status === 'queued' || t.status === 'running') {
          t.status = 'skipped';
        }
      }
      this.liveTests = this.liveTests;
      if (this._unsubscribeWs) {
        this._unsubscribeWs();
        this._unsubscribeWs = null;
      }
      // Snapshot live data as historical so it survives the mode transition.
      // Telemetry JSONL files may not have been flushed when the K8s job was
      // killed, so the in-memory data is likely all we have.
      this._snapshotLiveData();
      await this.fetchRun();
      this.fetchArtifacts();
      this.fetchTelemetryManifest();
    } catch (err: unknown) {
      this.error = err instanceof Error ? err.message : 'Failed to cancel run';
    } finally {
      this.cancelling = false;
    }
  }

  async triggerRun(): Promise<void> {
    this.triggering = true;
    try {
      await api.post(`/v2/runs/${this._runId}/trigger`, {
        firmwareVersion: this.triggerFwVersion.trim(),
      });
      this.showTrigger = false;
      this.triggerFwVersion = '';
      this.fetchRun();
    } catch (err: unknown) {
      this.error = err instanceof Error ? err.message : 'Failed to trigger run';
    } finally {
      this.triggering = false;
    }
  }

  async startDemo(scenario: string): Promise<void> {
    this.simulating = true;
    this.liveTests = [];
    this.liveRunning = false;
    this.liveFinished = false;
    this.liveSummary = null;
    this.selectedStage = null;

    try {
      await api.post(`/v2/runs/${this._runId}/demo/simulate?speed=0.1&scenario=${scenario}`);
    } catch (err: unknown) {
      this.error = err instanceof Error ? err.message : 'Failed to start demo';
      this.simulating = false;
    }
  }

  async fetchArtifacts(): Promise<void> {
    this.artifactsLoading = true;
    try {
      const res = await apiFetch<ApiResponse<Artifact[]>>(`/v2/runs/${this._runId}/artifacts`);
      this.artifacts = res.data;
      this.loadTelemetryFromArtifacts(res.data);
      this.loadRunningTestOutput(res.data);
    } catch {
      this.artifacts = [];
    } finally {
      this.artifactsLoading = false;
    }
  }

  async loadRunningTestOutput(arts: Artifact[]): Promise<void> {
    const runningTest = this.liveTests.find(t => t.status === 'running' && !t.logOutput);
    if (!runningTest) return;

    const outputLog = arts.find(a => a.name === 'logs/output.log');
    if (!outputLog) return;

    try {
      let text: string;
      try {
        const headers: Record<string, string> = {};
        const token = getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch(`/v2/runs/${this._runId}/artifacts/logs/output.log`, { headers });
        if (!res.ok) return;
        text = await res.text();
      } catch { return; }
      if (!text || text.startsWith('{')) return;

      const lines = text.split('\n');
      const testOutput = lines.slice(-500).join('\n').trim();
      if (testOutput) {
        runningTest.logOutput = testOutput;
        this.liveTests = this.liveTests;
      }
    } catch {
      // Ignore
    }
  }

  async loadTelemetryFromArtifacts(arts: Artifact[]): Promise<void> {
    const telemetryArts = arts.filter(a => a.name.startsWith('telemetry/') && a.name.endsWith('.jsonl'));
    const uartArts = arts.filter(a => a.name.endsWith('_uart.log'));
    const artList = telemetryArts.length > 0 ? telemetryArts : uartArts;
    if (artList.length === 0) return;

    const appLines: string[] = [];
    const commsLines: string[] = [];
    const power: PowerSample[] = [];

    for (const art of artList) {
      try {
        const headers: Record<string, string> = {};
        const token = getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`/v2/runs/${this._runId}/artifacts/${art.name}`, { headers });
        if (!res.ok) continue;
        const text = await res.text();
        if (!text) continue;

        if (art.name.endsWith('.jsonl')) {
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
            } catch { /* skip */ }
          }
        } else {
          const header = `\u2500\u2500 ${art.name} \u2500\u2500`;
          const lines = text.split('\n').filter(l => l.length > 0);
          appLines.push(header, ...lines);
          commsLines.push(header, ...lines);
        }
      } catch { /* skip */ }
    }

    if (appLines.length > MAX_UART_LINES) {
      const truncated = appLines.length - MAX_UART_LINES;
      this.uartAppLines = [`--- ${truncated.toLocaleString()} earlier lines truncated ---`, ...appLines.slice(-MAX_UART_LINES)];
    } else if (appLines.length > 0) {
      this.uartAppLines = appLines;
    }
    if (commsLines.length > MAX_UART_LINES) {
      const truncated = commsLines.length - MAX_UART_LINES;
      this.uartCommsLines = [`--- ${truncated.toLocaleString()} earlier lines truncated ---`, ...commsLines.slice(-MAX_UART_LINES)];
    } else if (commsLines.length > 0) {
      this.uartCommsLines = commsLines;
    }
    if (power.length > 300) {
      const cutoff = power[power.length - 1].t - 120;
      this.powerSamples = power.filter(s => s.t > cutoff);
    } else if (power.length > 0) {
      this.powerSamples = power;
    }
  }

  async fetchTelemetryManifest(): Promise<void> {
    try {
      const res = await apiFetch<{ data: TelemetryManifest }>(`/v2/runs/${this._runId}/telemetry/manifest`);
      if (res.data) {
        this.telemetryManifest = res.data;
        if (this.slotCtx) this.slotCtx.telemetryManifest = res.data;
        await this.loadTelemetryChannels();
      }
    } catch {
      this.telemetryManifest = null;
    }
  }

  async loadTelemetryChannels(): Promise<void> {
    if (!this.telemetryManifest) return;
    this.telemetryLoading = true;
    try {
      const headers: Record<string, string> = {};
      const token = getToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const channelEntries = Object.entries(this.telemetryManifest.channels);
      await Promise.all(channelEntries.map(async ([name, _info]) => {
        try {
          const res = await fetch(`/v2/runs/${this._runId}/telemetry/${name}`, { headers });
          if (!res.ok) return;
          const text = await res.text();
          if (!text) return;

          if (name === 'power' || name === 'power_chg') {
            const samples: PowerSample[] = [];
            for (const line of text.split('\n')) {
              if (!line.trim()) continue;
              try {
                const s = JSON.parse(line);
                samples.push({ t: s.t, mA: s.mA, mV: s.mV });
              } catch { /* skip malformed */ }
            }
            if (name === 'power') this.historicalPower = samples;
            else this.historicalPowerChg = samples;
          } else if (name === 'power_js') {
            const samples: JoulescopeSample[] = [];
            for (const line of text.split('\n')) {
              if (!line.trim()) continue;
              try {
                const s = JSON.parse(line);
                samples.push({ t: s.t, uA: s.uA ?? 0, mV: s.mV ?? 0, nA: s.nA });
              } catch { /* skip malformed */ }
            }
            this.historicalPowerJs = samples;
          } else if (name === 'uart_app' || name === 'uart_comms') {
            const tsLines: TimestampedLine[] = [];
            for (const line of text.split('\n')) {
              if (!line.trim()) continue;
              try {
                const s = JSON.parse(line);
                const ts = new Date(s.t * 1000).toISOString().slice(11, 23);
                tsLines.push({ t: s.t, line: `\x1b[36m[${ts}]\x1b[0m ${s.line}` });
              } catch { /* skip malformed */ }
            }
            if (name === 'uart_app') this.historicalUartAppTs = tsLines;
            else this.historicalUartCommsTs = tsLines;
          }
        } catch { /* skip failed channels */ }
      }));
      // Sync historical data to SlotContext
      if (this.slotCtx) {
        this.slotCtx.historicalPower = this.historicalPower;
        this.slotCtx.historicalPowerChg = this.historicalPowerChg;
        this.slotCtx.historicalPowerJs = this.historicalPowerJs;
        this.slotCtx.uartAppLines = this.historicalUartAppTs.map(l => l.line);
        this.slotCtx.uartCommsLines = this.historicalUartCommsTs.map(l => l.line);
        this.slotCtx.telemetryLoading = false;
      }
    } finally {
      this.telemetryLoading = false;
    }
  }

  // ── Live-data snapshot ──────────────────────────────────────────────

  /**
   * Preserve in-memory live data as historical data.
   * Called on run finish or cancel so that the data survives the transition
   * from live to analysis mode (telemetry artifacts may not exist yet).
   */
  private _snapshotLiveData(): void {
    if (this.historicalPower.length === 0 && this.powerSamples.length > 0) {
      this.historicalPower = [...this.powerSamples];
    }
    if (this.historicalPowerChg.length === 0 && this.powerChgSamples.length > 0) {
      this.historicalPowerChg = [...this.powerChgSamples];
    }
    // Live UART lines don't have timestamps, so also populate the plain
    // arrays which effectiveUart* falls back to.
    if (this.uartAppLines.length > 0 && this.historicalUartAppTs.length === 0) {
      // Keep the live lines in uartAppLines — effectiveUartApp will use them
      // as fallback when historicalUartAppTs is empty.
    }
  }

  // ── Artifact helpers ──────────────────────────────────────────────

  formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  isLogFile(name: string): boolean {
    return /\.(log|txt|uart|csv)$/i.test(name);
  }

  async viewLog(artifact: Artifact): Promise<void> {
    if (this.logArtifactName === artifact.name) {
      this.logContent = null;
      this.logArtifactName = null;
      return;
    }
    try {
      const res = await fetch(`/v2/runs/${this._runId}/artifacts/${artifact.name}`);
      if (res.redirected) {
        const textRes = await fetch(res.url);
        this.logContent = await textRes.text();
      } else {
        this.logContent = await res.text();
      }
      this.logArtifactName = artifact.name;
    } catch {
      this.logContent = 'Failed to load log file.';
      this.logArtifactName = artifact.name;
    }
  }

  // ── WebSocket setup ───────────────────────────────────────────────

  private setupWebSocket(): void {
    if (!this._runId) return;
    this._unsubscribeWs = subscribeRunWithLogs(
      this._runId,
      {
        onTestStart: (data: ValidationTestStartEvent) => {
          this.liveRunning = true;
          const testName = data.name || data.testName || '';
          const existing = this.findTest(testName, data.module);
          if (existing) {
            existing.status = 'running';
            existing.startedAtMs = Date.now();
          } else {
            this.liveTests.push({
              name: testName,
              module: data.module,
              status: 'running',
              durationS: null,
              startedAtMs: Date.now(),
              errorMessage: null,
              measurements: null,
              logOutput: null,
              expanded: false,
            });
            this.liveTests = this.liveTests;
          }
          if (data.module && data.module !== this.selectedStage) {
            this.selectedStage = data.module;
          }
          if (this.autoFollow) {
            for (const t of this.liveTests) {
              t.expanded = (t.name === testName && (data.module ? t.module === data.module : true));
            }
            this.liveTests = this.liveTests;
            setTimeout(() => this._scrollToTest(testName, data.module ?? null, 10), 150);
          }
          // Sync to SlotContext
          if (this.slotCtx) this.slotCtx.handleTestStart(data);
        },
        onTestResult: (data: ValidationTestResultEvent) => {
          const testName = data.name || data.testName || '';
          const existing = this.findTest(testName, data.module);
          if (existing) {
            existing.status = data.skipped ? 'skipped' : data.passed ? 'passed' : 'failed';
            existing.durationS = data.durationMs != null ? data.durationMs / 1000 : (data.durationS ?? null);
            existing.errorMessage = data.errorMessage;
            existing.measurements = data.measurements;
            existing.logOutput = data.logOutput;
            if (!data.passed && !data.skipped) {
              existing.expanded = true;
              const mod = data.module || existing.module;
              let afterFailed = false;
              for (const t of this.liveTests) {
                if (t === existing || (t.name === existing.name && t.module === existing.module)) {
                  afterFailed = true;
                  continue;
                }
                if (afterFailed && (!mod || t.module === mod) && (t.status === 'queued' || t.status === 'running')) {
                  t.status = 'skipped';
                }
              }
            } else if (this.autoFollow) {
              existing.expanded = false;
            }
            this.liveTests = this.liveTests;
          }
          // Sync to SlotContext
          if (this.slotCtx) this.slotCtx.handleTestResult(data);
        },
        onRunFinish: (data: ValidationRunFinishEvent) => {
          this.liveRunning = false;
          this.liveFinished = true;
          this.simulating = false;
          this.liveSummary = {
            total: data.total,
            passed: data.passed,
            failed: data.failed,
            errors: data.errors,
            durationS: data.durationMs != null ? data.durationMs / 1000 : (data.durationS ?? null),
          };
          // Snapshot live data before fetching artifacts/telemetry so it's
          // available as fallback if the telemetry files haven't been written yet.
          this._snapshotLiveData();
          if (this.slotCtx) this.slotCtx.handleRunFinish();
          this.fetchRun();
          this.fetchArtifacts();
        },
        onLogChunk: (data: ValidationLogChunkEvent) => {
          try {
            const text = data.data ? atob(data.data) : (data.chunk || '');
            if (!text) return;
            this._logChunkPending += text;
            this._scheduleFlush();
          } catch {
            // Ignore decode errors
          }
        },
        onTestList: (data) => {
          if (this.liveTests.length === 0 || this.liveTests.every(t => t.status === 'queued')) {
            const tests: LiveTest[] = data.tests.map(t => ({
              name: t.name,
              module: t.module,
              status: 'queued' as const,
              durationS: null,
              startedAtMs: null,
              errorMessage: null,
              measurements: null,
              logOutput: null,
              expanded: false,
            }));
            tests.sort((a, b) => a.name.localeCompare(b.name));
            this.liveTests = tests;
          }
        },
        onTelemetry: (data: TelemetryEvent) => {
          let powerChanged = false;

          for (const s of data.samples) {
            if (s.type === 'uart') {
              const ts = new Date(s.t * 1000).toISOString().slice(11, 23);
              const formatted = `\x1b[36m[${ts}]\x1b[0m ${s.line}`;
              if (s.target === 'app') this._uartAppPending.push(formatted);
              else if (s.target === 'comms') this._uartCommsPending.push(formatted);
            } else if (s.type === 'power') {
              this.powerSamples.push({ t: s.t!, mA: s.mA!, mV: s.mV! });
              powerChanged = true;
            } else if (s.type === 'power_chg') {
              this.powerChgSamples.push({ t: s.t!, mA: s.mA!, mV: s.mV! });
              powerChanged = true;
            } else if (s.type === 'power_js') {
              const js = s as typeof s & { uA?: number; mV?: number; nA?: number };
              this.powerJsSamples.push({
                t: s.t!,
                uA: js.uA ?? 0,
                mV: js.mV ?? 0,
                nA: js.nA,
              });
              powerChanged = true;
            } else if (s.type === 'accel') {
              const a = s as typeof s & { x?: number; y?: number; z?: number };
              this.accelSamples.push({ t: s.t!, x: a.x ?? 0, y: a.y ?? 0, z: a.z ?? 0 });
            }
          }

          if (powerChanged) {
            const cutoff = (this.powerSamples.at(-1)?.t ?? 0) - 60;
            if (this.powerSamples.length > 120) this.powerSamples = this.powerSamples.filter(s => s.t > cutoff).slice(-120);
            if (this.powerChgSamples.length > 120) this.powerChgSamples = this.powerChgSamples.filter(s => s.t > cutoff).slice(-120);
            if (this.powerJsSamples.length > 120) this.powerJsSamples = this.powerJsSamples.filter(s => s.t > cutoff).slice(-120);
            this.powerSamples = this.powerSamples;
            this.powerChgSamples = this.powerChgSamples;
            this.powerJsSamples = this.powerJsSamples;
          }

          // Trim accel samples to 60s sliding window + trigger reactivity
          if (this.accelSamples.length > 120) {
            const cutoff = (this.accelSamples.at(-1)?.t ?? 0) - 60;
            this.accelSamples = this.accelSamples.filter(s => s.t > cutoff).slice(-120);
          } else if (this.accelSamples.length > 0) {
            this.accelSamples = this.accelSamples; // trigger reactivity
          }

          if (this._uartAppPending.length > 0 || this._uartCommsPending.length > 0) this._scheduleFlush();

          // Sync to SlotContext
          if (this.slotCtx) this.slotCtx.handleTelemetry(data);
        },
      },
    );
  }

  // ── Auto-select first stage ───────────────────────────────────────

  autoSelectStage(): void {
    if (this.stages.length > 0 && !this.selectedStage) {
      const runningStage = this.stages.find(s => s.running > 0);
      const failedStage = this.stages.find(s => s.failed > 0);
      this.selectedStage = runningStage?.name || failedStage?.name || this.stages[0].name;
    }
  }

  // ── Initial focus on running test ─────────────────────────────────

  tryInitialFocus(): void {
    if (this._initialFocusDone || !this.run || this.run.status !== 'ACTIVE') return;
    const runningTest = this.liveTests.find(t => t.status === 'running');
    if (!runningTest) return;
    this._initialFocusDone = true;
    this.autoFollow = true;
    this.liveRunning = true;

    if (runningTest.module && runningTest.module !== this.selectedStage) {
      this.selectedStage = runningTest.module;
    }

    for (const t of this.liveTests) {
      t.expanded = (t === runningTest);
    }
    this.liveTests = this.liveTests;

    // Delay scroll to give Svelte time to render the expanded test and its log output.
    // The DOM needs to update before we can measure element positions.
    setTimeout(() => this._scrollToTest(runningTest.name, runningTest.module, 30), 200);
  }

  /** Scroll the test list panel so the target test is the FIRST visible item.
   *  Retries via setTimeout if the DOM element isn't rendered yet. */
  _scrollToTest(name: string, module: string | null, attempts: number): void {
    const tryScroll = (remaining: number) => {
      const el = document.querySelector(`[data-test-name="${name}"][data-test-module="${module}"]`) as HTMLElement;
      if (el) {
        // Walk up to find the scrollable panel
        let panel: HTMLElement | null = el.parentElement;
        while (panel && panel.scrollHeight <= panel.clientHeight) {
          panel = panel.parentElement;
        }
        if (panel) {
          // Sum up offset from element to the scroll container
          let offset = 0;
          let node: HTMLElement | null = el;
          while (node && node !== panel) {
            offset += node.offsetTop;
            node = node.offsetParent as HTMLElement | null;
            // If offsetParent jumped past panel, recalculate
            if (node && !panel.contains(node)) break;
          }
          panel.scrollTop = offset;
        } else {
          // Fallback: just use scrollIntoView
          el.scrollIntoView({ block: 'start' });
        }
      } else if (remaining > 0) {
        setTimeout(() => tryScroll(remaining - 1), 50);
      }
    };
    tryScroll(attempts);
  }

  // ── Telemetry fetch on completion ─────────────────────────────────

  checkTelemetryFetch(): void {
    if (this.run && (this.run.status as string) !== 'ACTIVE' && (this.run.status as string) !== 'PENDING' && !this._telemetryFetched) {
      this._telemetryFetched = true;
      this.fetchTelemetryManifest();
    }
  }

  // ── Handle selectedRange change for auto-expand ───────────────────

  handleRangeChange(): void {
    // Works in BOTH live and analysis mode — find the step matching the selected range
    const manifest = this.activeManifest;
    if (!manifest || !this.selectedRange) return;

    const step = manifest.steps.find(
      s => Math.abs(s.startedAt - this.selectedRange!.start) < 1 && Math.abs(s.finishedAt - this.selectedRange!.end) < 1
    );
    if (!step) return;

    if (step.module && step.module !== this.selectedStage) {
      this.selectedStage = step.module;
    }

    for (const t of this.liveTests) {
      t.expanded = (t.name === step.name && t.module === step.module);
    }
    this.liveTests = this.liveTests;

    setTimeout(() => this._scrollToTest(step.name, step.module, 10), 50);
  }

  // ── Lifecycle ─────────────────────────────────────────────────────

  subscribe(): void {
    this.fetchRun();
    this.fetchArtifacts();
    this.setupWebSocket();

    this._pollInterval = setInterval(() => {
      if (this.run?.status === 'ACTIVE' && !this.liveRunning) this.fetchRun();
    }, 5000);
    this._clockInterval = setInterval(() => { this.nowMs = Date.now(); }, 1000);
  }

  destroy(): void {
    if (this._pollInterval) { clearInterval(this._pollInterval); this._pollInterval = null; }
    if (this._clockInterval) { clearInterval(this._clockInterval); this._clockInterval = null; }
    if (this._unsubscribeWs) { this._unsubscribeWs(); this._unsubscribeWs = null; }
    if (this._flushTimer) { clearTimeout(this._flushTimer); this._flushTimer = null; }
    if (this.slotCtx) { this.slotCtx.destroy(); this.slotCtx = null; }
  }
}

// ── Context helpers ─────────────────────────────────────────────────

const RUN_CTX_KEY = Symbol('run-context');

export function createRunContext(runId: string): RunContext {
  const ctx = new RunContext(runId);
  setContext(RUN_CTX_KEY, ctx);
  return ctx;
}

export function getRunContext(): RunContext {
  return getContext<RunContext>(RUN_CTX_KEY);
}

export { RunContext };
