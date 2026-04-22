/**
 * Per-slot state management for test execution UI.
 *
 * Each SlotContext holds the test executions, UART logs, and telemetry
 * data for a single fixture slot / RunTarget. Works for both validation
 * (single slot) and manufacturing (N slots per panel).
 *
 * The UI is a passive observer — tests run in K8s independent of the browser.
 * SlotContext handles page reloads, late joins, and WebSocket reconnects
 * by reconstructing state from the API and layering live events on top.
 */

import { getContext, setContext } from 'svelte';
import type { RunTarget, TestExecution, TestStep } from '$lib/types/models';
import type { PowerSample, JoulescopeSample, AccelSample } from '$lib/components/validation/types';
import type { TelemetryManifest, TimeRange, StepInfo } from '$lib/components/validation/time-context';

// ── Shared interfaces ────────────────────────────────────────

export interface SlotLiveTest {
  name: string;
  module: string | null;
  status: 'queued' | 'running' | 'passed' | 'failed' | 'skipped';
  durationS: number | null;
  startedAtMs: number | null;
  errorMessage: string | null;
  measurements: Record<string, unknown> | null;
  logOutput: string | null;
  expanded: boolean;
  steps: SlotTestStep[];
  [key: string]: unknown;
}

export interface SlotTestStep {
  index: number;
  name: string;
  status: 'pending' | 'running' | 'passed' | 'failed';
  passed: boolean | null;
  durationMs: number | null;
  errorMessage: string | null;
  measurements: Record<string, unknown> | null;
}

export interface SlotStage {
  name: string;
  tests: SlotLiveTest[];
  passed: number;
  failed: number;
  skipped: number;
  running: number;
  durationS: number;
}

// ── Context key ──────────────────────────────────────────────

const SLOT_CTX_KEY = 'slot-execution-context';

export function setSlotContext(ctx: SlotContext): void {
  setContext(SLOT_CTX_KEY, ctx);
}

export function getSlotContext(): SlotContext {
  return getContext<SlotContext>(SLOT_CTX_KEY);
}

// ── SlotContext class ────────────────────────────────────────

const MAX_UART_LINES = 1500;

export class SlotContext {
  // ── Identity ─────────────────────────────────────────────
  readonly targetId: string;
  readonly slotIndex: number;
  serialNumber = $state('');
  deviceId = $state('');
  status = $state<RunTarget['status']>('PENDING');

  // ── Lifecycle flags ──────────────────────────────────────
  hydrated = $state(false);
  connected = $state(true);

  // ── Live test state ──────────────────────────────────────
  liveTests = $state<SlotLiveTest[]>([]);
  liveRunning = $state(false);
  liveFinished = $state(false);

  // ── UART lines ───────────────────────────────────────────
  uartAppLines = $state<string[]>([]);
  uartCommsLines = $state<string[]>([]);
  private _uartAppPending: string[] = [];
  private _uartCommsPending: string[] = [];
  private _flushTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Telemetry samples ────────────────────────────────────
  powerSamples = $state<PowerSample[]>([]);
  powerChgSamples = $state<PowerSample[]>([]);
  powerJsSamples = $state<JoulescopeSample[]>([]);
  accelSamples = $state<AccelSample[]>([]);
  private _lastPowerT = 0;

  // ── Post-analysis state ──────────────────────────────────
  telemetryManifest = $state<TelemetryManifest | null>(null);
  historicalPower = $state<PowerSample[]>([]);
  historicalPowerChg = $state<PowerSample[]>([]);
  historicalPowerJs = $state<JoulescopeSample[]>([]);
  telemetryLoading = $state(false);

  // ── UI state ─────────────────────────────────────────────
  selectedStage = $state<string | null>(null);
  selectedRange = $state<TimeRange | null>(null);
  autoFollow = $state(true);
  nowMs = $state(Date.now());
  private _clockInterval: ReturnType<typeof setInterval> | null = null;

  // ── Layout state ─────────────────────────────────────────
  sidebarWidth = $state(192);
  chartsWidth = $state(576);
  topPanelHeight = $state(50);
  resizing = $state(false);
  vResizing = $state<'sidebar' | 'charts' | null>(null);

  readonly POWER_WINDOW_S = 60;

  // ── Derived values ───────────────────────────────────────

  readonly analysisMode = $derived(
    this.liveFinished && !this.liveRunning
  );

  readonly stages = $derived.by((): SlotStage[] => {
    const stageMap = new Map<string, SlotStage>();
    for (const test of this.liveTests) {
      const stageName = test.module || 'Tests';
      if (!stageMap.has(stageName)) {
        stageMap.set(stageName, {
          name: stageName,
          tests: [],
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
    return Array.from(stageMap.values()).sort((a, b) => a.name.localeCompare(b.name));
  });

  readonly selectedStageData = $derived(
    this.stages.find(s => s.name === this.selectedStage) || null
  );

  readonly livePassedCount = $derived(this.liveTests.filter(t => t.status === 'passed').length);
  readonly liveFailedCount = $derived(this.liveTests.filter(t => t.status === 'failed').length);
  readonly liveSkippedCount = $derived(this.liveTests.filter(t => t.status === 'skipped').length);
  readonly liveCompletedCount = $derived(this.livePassedCount + this.liveFailedCount + this.liveSkippedCount);

  readonly liveManifest = $derived.by((): TelemetryManifest | null => {
    if (this.liveTests.length === 0) return null;
    const steps: StepInfo[] = [];
    const now = this.nowMs / 1000;
    let earliest = now;
    for (const t of this.liveTests) {
      if (t.status === 'queued') continue;
      const startS = t.startedAtMs ? t.startedAtMs / 1000 : now;
      if (startS < earliest) earliest = startS;
      let endS: number;
      if (t.durationS !== null && t.durationS > 0) endS = startS + t.durationS;
      else if (t.status === 'running') endS = now;
      else endS = startS + 0.5;
      steps.push({ name: t.name, module: t.module, startedAt: startS, finishedAt: endS, status: t.status });
    }
    if (steps.length === 0) return null;
    return {
      version: 1,
      runId: this.targetId,
      startedAt: earliest,
      finishedAt: now,
      totalSamples: 0,
      channels: {},
      steps,
    };
  });

  readonly activeManifest = $derived(this.telemetryManifest ?? this.liveManifest);

  // Filtered data (when a time range is selected)
  readonly effectivePower = $derived.by(() => {
    const src = this.analysisMode ? this.historicalPower : this.powerSamples;
    if (!this.selectedRange) return src;
    return src.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
  });

  readonly effectivePowerChg = $derived.by(() => {
    const src = this.analysisMode ? this.historicalPowerChg : this.powerChgSamples;
    if (!this.selectedRange) return src;
    return src.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
  });

  readonly effectivePowerJs = $derived.by(() => {
    const src = this.analysisMode ? this.historicalPowerJs : this.powerJsSamples;
    if (!this.selectedRange) return src;
    return src.filter(s => s.t >= this.selectedRange!.start && s.t <= this.selectedRange!.end);
  });

  readonly effectiveUartApp = $derived(this.uartAppLines);
  readonly effectiveUartComms = $derived(this.uartCommsLines);

  // ── Constructor ──────────────────────────────────────────

  constructor(targetId: string, slotIndex: number, serialNumber?: string) {
    this.targetId = targetId;
    this.slotIndex = slotIndex;
    this.serialNumber = serialNumber || '';
  }

  // ── Lifecycle ────────────────────────────────────────────

  startClock(): void {
    if (this._clockInterval) return;
    this._clockInterval = setInterval(() => { this.nowMs = Date.now(); }, 1000);
  }

  destroy(): void {
    if (this._clockInterval) {
      clearInterval(this._clockInterval);
      this._clockInterval = null;
    }
    if (this._flushTimer) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
  }

  // ── Hydration from API ───────────────────────────────────
  // Called on page load and after WebSocket reconnect.
  // Reconstructs liveTests from persisted TestExecution records.
  // Idempotent: merges with existing state (API is authoritative
  // for status/measurements, preserves buffered UART lines).

  hydrateFromTarget(target: RunTarget): void {
    this.serialNumber = target.serialNumber || '';
    this.deviceId = target.deviceId || '';
    this.status = target.status;

    if (!target.executions?.length) {
      this.hydrated = true;
      return;
    }

    const existingMap = new Map<string, SlotLiveTest>();
    for (const t of this.liveTests) {
      existingMap.set(`${t.module || ''}::${t.name}`, t);
    }

    const tests: SlotLiveTest[] = [];
    for (const exec of target.executions) {
      const key = `${exec.module || ''}::${exec.name}`;
      const existing = existingMap.get(key);

      const status = _mapStatus(exec.status);
      const steps = (exec.steps || []).map((s: TestStep) => ({
        index: s.stepIndex,
        name: s.name,
        status: s.passed ? 'passed' as const : s.status === 'RUNNING' ? 'running' as const : s.status === 'FAILED' || s.status === 'ERROR' ? 'failed' as const : 'pending' as const,
        passed: s.passed ?? null,
        durationMs: s.durationMs ?? null,
        errorMessage: s.errorMessage ?? null,
        measurements: s.measurements as Record<string, unknown> | null ?? null,
      }));

      tests.push({
        name: exec.name,
        module: exec.module || null,
        status,
        durationS: exec.durationMs ? exec.durationMs / 1000 : null,
        startedAtMs: exec.startedAt ? new Date(exec.startedAt).getTime() : null,
        errorMessage: exec.errorMessage ?? null,
        measurements: exec.measurements as Record<string, unknown> | null ?? null,
        logOutput: existing?.logOutput ?? exec.logOutput ?? null,
        expanded: existing?.expanded ?? (status === 'failed'),
        steps,
      });
    }

    this.liveTests = tests;

    // Update lifecycle flags
    const hasRunning = tests.some(t => t.status === 'running');
    const allDone = tests.every(t => t.status !== 'queued' && t.status !== 'running');
    this.liveRunning = hasRunning;
    this.liveFinished = allDone && tests.length > 0;

    // Auto-select stage of running test
    if (hasRunning && !this.selectedStage) {
      const running = tests.find(t => t.status === 'running');
      if (running?.module) this.selectedStage = running.module;
    }
    if (!this.selectedStage && this.stages.length > 0) {
      this.selectedStage = this.stages[0].name;
    }

    this.hydrated = true;
  }

  // ── WebSocket event handlers (idempotent) ────────────────

  handleTestStart(data: { name?: string; testName?: string; module?: string | null; targetId?: string }): void {
    const name = data.name || data.testName || '';
    if (!name) return;
    const module = data.module || null;

    // Idempotent: skip if already exists with non-queued status
    const existing = this.liveTests.find(t => t.name === name && t.module === module);
    if (existing && existing.status !== 'queued') return;

    if (existing) {
      existing.status = 'running';
      existing.startedAtMs = Date.now();
    } else {
      this.liveTests.push({
        name,
        module,
        status: 'running',
        durationS: null,
        startedAtMs: Date.now(),
        errorMessage: null,
        measurements: null,
        logOutput: null,
        expanded: false,
        steps: [],
      });
    }

    this.liveRunning = true;

    // Auto-follow: collapse previous, expand this one
    if (this.autoFollow) {
      for (const t of this.liveTests) {
        t.expanded = (t.name === name && t.module === module);
      }
      if (module && module !== this.selectedStage) {
        this.selectedStage = module;
      }
    }

    this.liveTests = this.liveTests;
  }

  handleTestResult(data: {
    name?: string; testName?: string; module?: string | null;
    passed: boolean; durationMs?: number | null; durationS?: number | null;
    errorMessage?: string | null; measurements?: Record<string, unknown> | null;
    logOutput?: string | null;
    skipped?: boolean;
  }): void {
    const name = data.name || data.testName || '';
    if (!name) return;
    const module = data.module || null;

    const test = this.liveTests.find(t => t.name === name && t.module === module);
    if (!test) {
      // Late result for unknown test — create it
      const status = data.skipped ? 'skipped' : data.passed ? 'passed' : 'failed';
      this.liveTests.push({
        name,
        module,
        status,
        durationS: data.durationMs ? data.durationMs / 1000 : data.durationS ?? null,
        startedAtMs: null,
        errorMessage: data.errorMessage ?? null,
        measurements: data.measurements ?? null,
        logOutput: data.logOutput ?? null,
        expanded: status === 'failed',
        steps: [],
      });
      this.liveTests = this.liveTests;
      return;
    }

    // Idempotent: don't downgrade terminal status
    if (test.status === 'passed' || test.status === 'failed' || test.status === 'skipped') return;

    test.status = data.skipped ? 'skipped' : data.passed ? 'passed' : 'failed';
    test.durationS = data.durationMs ? data.durationMs / 1000 : data.durationS ?? test.durationS;
    test.errorMessage = data.errorMessage ?? test.errorMessage;
    test.measurements = data.measurements ?? test.measurements;
    if (data.logOutput) test.logOutput = data.logOutput;

    if (test.status === 'failed') {
      test.expanded = true;
    }

    this.liveTests = this.liveTests;
  }

  handleStepResult(data: {
    testName?: string; name?: string; module?: string | null;
    stepIndex: number; stepName?: string;
    passed: boolean; durationMs?: number;
    errorMessage?: string | null; measurements?: Record<string, unknown> | null;
  }): void {
    const testName = data.testName || data.name || '';
    const test = this.liveTests.find(t => t.name === testName);
    if (!test) return;

    const step: SlotTestStep = {
      index: data.stepIndex,
      name: data.stepName || `Step ${data.stepIndex}`,
      status: data.passed ? 'passed' : 'failed',
      passed: data.passed,
      durationMs: data.durationMs ?? null,
      errorMessage: data.errorMessage ?? null,
      measurements: data.measurements ?? null,
    };

    const existing = test.steps.findIndex(s => s.index === data.stepIndex);
    if (existing >= 0) {
      test.steps[existing] = step;
    } else {
      test.steps.push(step);
      test.steps.sort((a, b) => a.index - b.index);
    }

    this.liveTests = this.liveTests;
  }

  handleLogChunk(data: { file?: string; data?: string; lines?: string[] }): void {
    // In multi-slot runs, UART data arrives via the telemetry path (handleTelemetry
    // with type=uart), properly routed by targetId/slotIndex. Log chunks are pytest
    // stdout capture and would duplicate UART content already delivered via telemetry.
    // Skip UART panel injection when telemetry is active (indicated by having received
    // any UART lines from telemetry).
    if (this.uartAppLines.length > 0 || this.uartCommsLines.length > 0 ||
        this._uartAppPending.length > 0 || this._uartCommsPending.length > 0) {
      return;
    }

    const file = data.file || '';
    const isComms = file.includes('comms') || file.includes('uart1') || file.includes('9151');

    let lines: string[] = [];
    if (data.lines) {
      lines = data.lines;
    } else if (data.data) {
      try {
        const decoded = atob(data.data);
        lines = decoded.split('\n').filter(l => l.length > 0);
      } catch {
        lines = data.data.split('\n').filter(l => l.length > 0);
      }
    }

    if (lines.length > 0) {
      if (isComms) {
        this._uartCommsPending.push(...lines);
      } else {
        this._uartAppPending.push(...lines);
      }
      this._scheduleFlush();
    }
  }

  handleTelemetry(data: { samples?: Array<Record<string, unknown>> }): void {
    if (!data.samples) return;
    let hasPower = false;
    let hasUart = false;

    for (const s of data.samples) {
      const t = (s.t as number) || 0;

      if (s.type === 'uart' && s.line) {
        // Route UART telemetry samples to the correct terminal
        const target = (s.target as string) || '';
        const isComms = target === 'comms' || target.includes('comms') || target.includes('9151');
        const ts = new Date(t * 1000).toISOString().slice(11, 23);
        const formatted = `\x1b[36m[${ts}]\x1b[0m ${s.line as string}`;
        if (isComms) {
          this._uartCommsPending.push(formatted);
        } else {
          this._uartAppPending.push(formatted);
        }
        hasUart = true;
      } else if (s.type === 'power' && s.mA !== undefined) {
        this.powerSamples.push({ t, mA: s.mA as number, mV: (s.mV as number) || 0 });
        this._lastPowerT = t;
        hasPower = true;
      } else if (s.type === 'power_chg' && s.mA !== undefined) {
        this.powerChgSamples.push({ t, mA: s.mA as number, mV: (s.mV as number) || 0 });
        hasPower = true;
      } else if (s.type === 'power_js' && s.uA !== undefined) {
        this.powerJsSamples.push({ t, uA: s.uA as number, mV: (s.mV as number) || 0, nA: s.nA as number | undefined });
        hasPower = true;
      } else if (s.type === 'accel' && s.x !== undefined) {
        this.accelSamples.push({ t, x: s.x as number, y: s.y as number, z: s.z as number });
      }
    }

    // Flush UART lines
    if (hasUart) {
      this._scheduleFlush();
    }

    if (hasPower) {
      // Trim to sliding window
      const cutoff = (Date.now() / 1000) - this.POWER_WINDOW_S * 2;
      if (this.powerSamples.length > 2000) {
        this.powerSamples = this.powerSamples.filter(s => s.t > cutoff);
      }

      // Trigger reactivity
      this.powerSamples = this.powerSamples;
      this.powerChgSamples = this.powerChgSamples;
      this.powerJsSamples = this.powerJsSamples;
      this.accelSamples = this.accelSamples;
    }
  }

  handleRunFinish(): void {
    this.liveRunning = false;
    this.liveFinished = true;
    for (const t of this.liveTests) {
      if (t.status === 'queued' || t.status === 'running') {
        t.status = 'skipped';
      }
    }
    this.liveTests = this.liveTests;
  }

  // ── UI helpers ───────────────────────────────────────────

  toggleTestExpanded(name: string, module?: string | null): void {
    const test = module
      ? this.liveTests.find(t => t.name === name && t.module === module)
      : this.liveTests.find(t => t.name === name);
    if (!test) return;

    test.expanded = !test.expanded;

    if (this.analysisMode && this.activeManifest && test.expanded) {
      const step = this.activeManifest.steps.find(s => s.name === name && s.module === module);
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

    this.liveTests = this.liveTests;
  }

  autoSelectStage(): void {
    if (this.selectedStage) return;
    if (this.stages.length > 0) {
      this.selectedStage = this.stages[0].name;
    }
  }

  // ── Internal ─────────────────────────────────────────────

  private _scheduleFlush(): void {
    if (this._flushTimer) return;
    this._flushTimer = setTimeout(() => {
      this._flushTimer = null;
      if (this._uartAppPending.length > 0) {
        this.uartAppLines = [...this.uartAppLines, ...this._uartAppPending].slice(-MAX_UART_LINES);
        this._uartAppPending = [];
      }
      if (this._uartCommsPending.length > 0) {
        this.uartCommsLines = [...this.uartCommsLines, ...this._uartCommsPending].slice(-MAX_UART_LINES);
        this._uartCommsPending = [];
      }
    }, 200);
  }
}

// ── Helpers ──────────────────────────────────────────────────

function _mapStatus(dbStatus: string): SlotLiveTest['status'] {
  switch (dbStatus) {
    case 'RUNNING': return 'running';
    case 'PASSED': return 'passed';
    case 'FAILED':
    case 'ERROR': return 'failed';
    case 'SKIPPED':
    case 'CANCELLED': return 'skipped';
    default: return 'queued';
  }
}
