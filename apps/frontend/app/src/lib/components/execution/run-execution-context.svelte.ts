/**
 * RunExecutionContext — unified run-level state for both validation and manufacturing.
 *
 * Manages one TestRun with N RunTargets (1 for validation, N for manufacturing).
 * Each target gets its own SlotContext. WebSocket events route to the correct slot
 * by targetId. Telemetry manifest loads into each slot for post-run analysis.
 *
 * Usage:
 *   const ctx = new RunExecutionContext({
 *     runId: 'abc',
 *     backPath: '/validation/runs',
 *     backLabel: 'Back to runs',
 *     permission: 'validation:view',
 *   });
 *   ctx.subscribe();    // fetch + WebSocket + polling
 *   ctx.destroy();      // cleanup
 */

import { getContext, setContext } from 'svelte';
import { apiFetch, api, getToken } from '$lib/api';
import { SlotContext } from './slot-context.svelte';
import {
  subscribeRunWithLogs,
  type ValidationTestStartEvent,
  type ValidationTestResultEvent,
  type ValidationRunFinishEvent,
  type ValidationLogChunkEvent,
  type TelemetryEvent,
} from '$lib/services/websocket';
import type { TestRun } from '$lib/types/models';
import type { ApiResponse } from '$lib/types';
import type { TelemetryManifest, TimeRange } from '$lib/components/validation/time-context';
import type { PowerSample, JoulescopeSample } from '$lib/components/validation/types';

// ── Config ────────────────────────────────────────────────────────────

export interface RunHardwareInfo {
  productName: string;
  boardRevision: string;
  firmwareVersion: string;
  socLabels: string[];
}

export interface RunExecutionConfig {
  runId: string;
  backPath: string;
  backLabel: string;
  permission: string;
  /** Extract hardware info from the fetched run. */
  getHardwareInfo?: (run: TestRun) => RunHardwareInfo;
}

// ── Timestamped UART line (for historical analysis) ───────────────────

interface TimestampedLine {
  t: number;
  line: string;
}

// ── Context class ─────────────────────────────────────────────────────

const MAX_UART_LINES = 1500;

export class RunExecutionContext {
  // Config (immutable after construction)
  readonly config!: RunExecutionConfig;

  // Core run state
  run = $state<TestRun | null>(null);
  loading = $state(true);
  error = $state<string | null>(null);

  // Per-slot contexts (one per RunTarget)
  slots = $state<SlotContext[]>([]);
  activeSlotIdx = $state(0);

  // Hardware info (extracted from run after fetch)
  productName = $state('');
  boardRevision = $state('');
  firmwareVersion = $state('');
  socLabels = $state<string[]>([]);

  // Cancel state
  cancelling = $state(false);
  confirmCancel = $state(false);
  cancelConfirmText = $state('');

  // Live clock (drives duration timers in UI)
  nowMs = $state(Date.now());

  // Lifecycle handles
  private _pollInterval: ReturnType<typeof setInterval> | null = null;
  private _clockInterval: ReturnType<typeof setInterval> | null = null;
  private _unsubscribeWs: (() => void) | null = null;
  private _telemetryFetched = false;
  private _initialFocusDone = false;

  // ── Derived values ──────────────────────────────────────────────

  readonly activeSlot = $derived(this.slots[this.activeSlotIdx] || null);
  readonly isActive = $derived(this.run?.status === 'ACTIVE');
  readonly isPending = $derived(this.run?.status === 'PENDING');
  readonly isComplete = $derived(
    !!this.run && this.run.status !== 'ACTIVE' && this.run.status !== 'PENDING'
  );
  readonly isMultiSlot = $derived(this.slots.length > 1);
  readonly runTitle = $derived(
    this.run?.panelIdentifier || this.run?.name || this.config.runId.slice(0, 8)
  );

  readonly slotTabs = $derived(this.slots.map((s) => ({
    index: s.slotIndex,
    label: `Slot ${s.slotIndex + 1}`,
    serialNumber: s.serialNumber || undefined,
    status: s.status,
  })));

  readonly durationMs = $derived.by(() => {
    if (!this.run?.startedAt) return null;
    const start = new Date(this.run.startedAt).getTime();
    const end = this.run.completedAt
      ? new Date(this.run.completedAt).getTime()
      : this.nowMs;
    return end - start;
  });

  // Aggregate counts across all slots
  readonly totalPassed = $derived(
    this.slots.reduce((sum, s) => sum + s.livePassedCount, 0)
  );
  readonly totalFailed = $derived(
    this.slots.reduce((sum, s) => sum + s.liveFailedCount, 0)
  );
  readonly totalSkipped = $derived(
    this.slots.reduce((sum, s) => sum + s.liveSkippedCount, 0)
  );
  readonly totalTests = $derived(
    this.slots.reduce((sum, s) => sum + s.liveTests.length, 0)
  );

  // ── Constructor ─────────────────────────────────────────────────

  constructor(config: RunExecutionConfig) {
    this.config = config;
  }

  get runId(): string {
    return this.config.runId;
  }

  // ── Lifecycle ───────────────────────────────────────────────────

  subscribe(): void {
    this._fetchRun();
    this._clockInterval = setInterval(() => { this.nowMs = Date.now(); }, 1000);
    this._pollInterval = setInterval(() => {
      if (this.isActive && !this.activeSlot?.liveRunning) {
        this._fetchRun();
      }
    }, 5000);
  }

  destroy(): void {
    if (this._pollInterval) { clearInterval(this._pollInterval); this._pollInterval = null; }
    if (this._clockInterval) { clearInterval(this._clockInterval); this._clockInterval = null; }
    if (this._unsubscribeWs) { this._unsubscribeWs(); this._unsubscribeWs = null; }
    for (const s of this.slots) s.destroy();
  }

  // ── Data fetching ───────────────────────────────────────────────

  private async _fetchRun(): Promise<void> {
    try {
      const res = await apiFetch<ApiResponse<TestRun>>(`/v2/runs/${this.config.runId}`);
      this.run = res.data;
      this.error = null;

      // Extract hardware info
      if (this.config.getHardwareInfo) {
        const hw = this.config.getHardwareInfo(res.data);
        this.productName = hw.productName;
        this.boardRevision = hw.boardRevision;
        this.firmwareVersion = hw.firmwareVersion;
        this.socLabels = hw.socLabels;
      }

      // Build slot contexts from targets (only on first fetch)
      const targets = res.data.targets || [];
      if (this.slots.length === 0 && targets.length > 0) {
        const built: SlotContext[] = [];
        for (const target of targets) {
          const slot = new SlotContext(
            target.id,
            target.slotIndex,
            target.serialNumber || '',
          );
          slot.hydrateFromTarget(target);
          slot.startClock();
          built.push(slot);
        }
        this.slots = built;

        // Hydrate test skeleton from config.testList — MERGE with any existing
        // execution data so page reloads mid-run show the full test plan, not
        // just the tests that have already started.
        const testList = (res.data.config as Record<string, unknown>)?.testList;
        if (testList && Array.isArray(testList)) {
          for (const slot of built) {
            const slotTests = (testList as { name: string; module: string | null }[]).filter(t => {
              const m = t.name?.match(/\[slot-(\d+)\]/);
              return m ? parseInt(m[1]) === slot.slotIndex : built.length === 1;
            });
            if (slotTests.length === 0) continue;

            if (slot.liveTests.length === 0) {
              // No executions yet — populate full skeleton
              slot.liveTests = slotTests.map(t => ({
                name: t.name,
                module: t.module,
                status: 'queued' as const,
                durationS: null,
                startedAtMs: null,
                errorMessage: null,
                measurements: null,
                logOutput: null,
                expanded: false,
                steps: [],
              }));
            } else {
              // Some executions exist — merge: add queued entries for tests
              // not already in liveTests so the full skeleton is visible
              const existingNames = new Set(slot.liveTests.map(t => t.name));
              for (const t of slotTests) {
                if (!existingNames.has(t.name)) {
                  slot.liveTests.push({
                    name: t.name,
                    module: t.module,
                    status: 'queued' as const,
                    durationS: null,
                    startedAtMs: null,
                    errorMessage: null,
                    measurements: null,
                    logOutput: null,
                    expanded: false,
                    steps: [],
                  });
                }
              }
              // Sort by testList order (preserves the test plan order)
              const orderMap = new Map(slotTests.map((t, i) => [t.name, i]));
              slot.liveTests.sort((a, b) =>
                (orderMap.get(a.name) ?? 999) - (orderMap.get(b.name) ?? 999)
              );
              slot.liveTests = slot.liveTests; // trigger reactivity
            }
            slot.hydrated = true;
          }
        }

        // Subscribe to WebSocket if run is active
        if (this.isActive || this.isPending) {
          this._setupWebSocket();
        }
      }

      // Check for telemetry on completed runs
      this._checkTelemetryFetch();
    } catch (err: unknown) {
      this.error = err instanceof Error ? err.message : 'Failed to load run';
    } finally {
      this.loading = false;
    }
  }

  // ── WebSocket ───────────────────────────────────────────────────

  private _setupWebSocket(): void {
    if (this._unsubscribeWs) return;

    this._unsubscribeWs = subscribeRunWithLogs(
      this.config.runId,
      {
        onTestStart: (data: ValidationTestStartEvent) => {
          const slot = this._findSlot(data.targetId);
          if (slot) {
            slot.handleTestStart(data);
            // Auto-scroll to the running test — use rAF to avoid lagging behind fast POST tests
            if (slot.autoFollow) {
              const name = data.name || data.testName || '';
              const module = data.module || null;
              requestAnimationFrame(() => this._scrollToTest(name, module, 10));
            }
          }
        },
        onTestResult: (data: ValidationTestResultEvent) => {
          const slot = this._findSlot(data.targetId);
          if (slot) slot.handleTestResult(data);
        },
        onRunFinish: (_data: ValidationRunFinishEvent) => {
          for (const s of this.slots) s.handleRunFinish();
          // Snapshot live data before fetching telemetry
          this._snapshotAllSlots();
          this._fetchRun();
        },
        onLogChunk: (data: ValidationLogChunkEvent) => {
          // Route to the target's slot, fall back to active slot
          const slot = this._findSlot(data.targetId) || this.activeSlot;
          if (slot) slot.handleLogChunk(data);
        },
        onTestList: (data) => {
          // Route test list to the correct slot by targetId (multi-slot),
          // or fall back to first slot (single-slot/validation)
          const targetId = data.targetId;
          const slot = targetId
            ? this.slots.find(s => s.targetId === targetId)
            : this.activeSlot || this.slots[0];

          if (slot && (slot.liveTests.length === 0 || slot.liveTests.every(t => t.status === 'queued'))) {
            slot.liveTests = data.tests.map((t: { name: string; module: string | null }) => ({
              name: t.name,
              module: t.module,
              status: 'queued' as const,
              durationS: null,
              startedAtMs: null,
              errorMessage: null,
              measurements: null,
              logOutput: null,
              expanded: false,
              steps: [],
            }));
            slot.hydrated = true;
          }
        },
        onTelemetry: (data: TelemetryEvent) => {
          // Route telemetry samples by targetId for per-slot power/UART
          if (data.samples && this.slots.length > 1) {
            // Group samples by targetId for multi-slot routing
            const byTarget = new Map<string, Array<Record<string, unknown>>>();
            const unrouted: Array<Record<string, unknown>> = [];

            for (const sample of data.samples) {
              const tid = (sample as Record<string, unknown>).targetId as string | undefined;
              if (tid) {
                if (!byTarget.has(tid)) byTarget.set(tid, []);
                byTarget.get(tid)!.push(sample as Record<string, unknown>);
              } else {
                unrouted.push(sample as Record<string, unknown>);
              }
            }

            // Deliver per-target batches to correct slots
            for (const [tid, samples] of byTarget) {
              const slot = this.slots.find(s => s.targetId === tid);
              if (slot) slot.handleTelemetry({ ...data, samples: samples as TelemetryEvent['samples'] });
            }

            // Unrouted samples go to active slot (backward compat / single-slot)
            if (unrouted.length > 0) {
              const slot = this.activeSlot;
              if (slot) slot.handleTelemetry({ ...data, samples: unrouted as TelemetryEvent['samples'] });
            }
          } else {
            // Single-slot: all samples to the only slot
            const slot = this._findSlotByTelemetry(data) || this.activeSlot;
            if (slot) slot.handleTelemetry(data);
          }
        },
      },
    );
  }

  private _findSlot(targetId?: string): SlotContext | undefined {
    if (!targetId) return this.activeSlot || this.slots[0];
    return this.slots.find((s) => s.targetId === targetId) || this.activeSlot;
  }

  private _findSlotByTelemetry(data: TelemetryEvent): SlotContext | undefined {
    // If telemetry samples include a target hint, route accordingly
    // Otherwise falls back to active slot
    const firstSample = data.samples?.[0];
    if (firstSample && 'targetId' in firstSample) {
      return this._findSlot((firstSample as Record<string, unknown>).targetId as string);
    }
    return undefined;
  }

  // ── Cancel ──────────────────────────────────────────────────────

  async cancelRun(): Promise<void> {
    this.cancelling = true;
    try {
      await api.post(`/v2/runs/${this.config.runId}/cancel`);

      // Mark remaining tests as skipped in all slots
      for (const slot of this.slots) {
        for (const t of slot.liveTests) {
          if (t.status === 'queued' || t.status === 'running') {
            t.status = 'skipped';
          }
        }
        slot.liveTests = slot.liveTests;
        slot.liveRunning = false;
        slot.liveFinished = true;
      }

      // Disconnect WebSocket
      if (this._unsubscribeWs) {
        this._unsubscribeWs();
        this._unsubscribeWs = null;
      }

      // Snapshot live data and re-fetch
      this._snapshotAllSlots();
      await this._fetchRun();
    } catch (err: unknown) {
      this.error = err instanceof Error ? err.message : 'Failed to cancel run';
    } finally {
      this.cancelling = false;
    }
  }

  // ── Telemetry (post-run analysis) ───────────────────────────────

  private _checkTelemetryFetch(): void {
    if (this.run && !this.isActive && !this.isPending && !this._telemetryFetched) {
      this._telemetryFetched = true;
      this._fetchTelemetryManifest();
    }
  }

  private async _fetchTelemetryManifest(): Promise<void> {
    try {
      const res = await apiFetch<{ data: TelemetryManifest }>(
        `/v2/runs/${this.config.runId}/telemetry/manifest`
      );
      if (!res.data) return;

      // Load manifest into each slot (single-slot: slot[0], multi-slot: all get same manifest)
      // TODO: per-slot manifests when backend supports per-target telemetry files
      for (const slot of this.slots) {
        slot.telemetryManifest = res.data;
      }

      await this._loadTelemetryChannels(res.data);
    } catch {
      // No manifest available — that's fine, historical data just won't be available
    }
  }

  private async _loadTelemetryChannels(manifest: TelemetryManifest): Promise<void> {
    const headers: Record<string, string> = {};
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    if (this.slots.length === 0) return;

    // Mark all slots as loading
    for (const s of this.slots) s.telemetryLoading = true;

    try {
      // Parse all channel data once, then distribute to all slots
      const channelEntries = Object.entries(manifest.channels);
      await Promise.all(channelEntries.map(async ([name, _info]) => {
        try {
          const res = await fetch(
            `/v2/runs/${this.config.runId}/telemetry/${name}`,
            { headers },
          );
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
            for (const slot of this.slots) {
              if (name === 'power') slot.historicalPower = samples;
              else slot.historicalPowerChg = samples;
            }
          } else if (name === 'power_js') {
            const samples: JoulescopeSample[] = [];
            for (const line of text.split('\n')) {
              if (!line.trim()) continue;
              try {
                const s = JSON.parse(line);
                samples.push({ t: s.t, uA: s.uA ?? 0, mV: s.mV ?? 0, nA: s.nA });
              } catch { /* skip malformed */ }
            }
            for (const slot of this.slots) {
              slot.historicalPowerJs = samples;
            }
          } else if (name === 'uart_app' || name === 'uart_comms') {
            const lines: string[] = [];
            for (const line of text.split('\n')) {
              if (!line.trim()) continue;
              try {
                const s = JSON.parse(line);
                const ts = new Date(s.t * 1000).toISOString().slice(11, 23);
                lines.push(`\x1b[36m[${ts}]\x1b[0m ${s.line}`);
              } catch { /* skip malformed */ }
            }
            for (const slot of this.slots) {
              if (name === 'uart_app') slot.uartAppLines = lines;
              else slot.uartCommsLines = lines;
            }
          }
        } catch { /* skip failed channels */ }
      }));
    } finally {
      for (const s of this.slots) s.telemetryLoading = false;
    }
  }

  // ── Snapshot live data ──────────────────────────────────────────

  private _snapshotAllSlots(): void {
    // Collect power samples from all slots (live telemetry may have landed on different slots)
    let allPower: PowerSample[] = [];
    let allPowerChg: PowerSample[] = [];
    for (const slot of this.slots) {
      if (slot.powerSamples.length > 0) allPower = [...allPower, ...slot.powerSamples];
      if (slot.powerChgSamples.length > 0) allPowerChg = [...allPowerChg, ...slot.powerChgSamples];
    }
    // Sort by timestamp and deduplicate
    allPower.sort((a, b) => a.t - b.t);
    allPowerChg.sort((a, b) => a.t - b.t);

    // Distribute to all slots that don't have historical data yet
    for (const slot of this.slots) {
      if (slot.historicalPower.length === 0 && allPower.length > 0) {
        slot.historicalPower = allPower;
      }
      if (slot.historicalPowerChg.length === 0 && allPowerChg.length > 0) {
        slot.historicalPowerChg = allPowerChg;
      }
    }
  }

  // ── Auto-focus helpers ──────────────────────────────────────────

  tryInitialFocus(): void {
    if (this._initialFocusDone || !this.run || !this.isActive) return;
    const slot = this.activeSlot;
    if (!slot) return;

    const runningTest = slot.liveTests.find(t => t.status === 'running');
    if (!runningTest) return;

    this._initialFocusDone = true;
    slot.autoFollow = true;
    slot.liveRunning = true;

    if (runningTest.module && runningTest.module !== slot.selectedStage) {
      slot.selectedStage = runningTest.module;
    }

    for (const t of slot.liveTests) {
      t.expanded = (t === runningTest);
    }
    slot.liveTests = slot.liveTests;

    setTimeout(() => {
      this._scrollToTest(runningTest.name, runningTest.module, 30);
    }, 200);
  }

  autoSelectStage(): void {
    const slot = this.activeSlot;
    if (!slot) return;
    slot.autoSelectStage();
  }

  handleRangeChange(): void {
    const slot = this.activeSlot;
    if (!slot) return;
    const manifest = slot.activeManifest;
    if (!manifest || !slot.selectedRange) return;

    const step = manifest.steps.find(
      s => Math.abs(s.startedAt - slot.selectedRange!.start) < 1
        && Math.abs(s.finishedAt - slot.selectedRange!.end) < 1
    );
    if (!step) return;

    if (step.module && step.module !== slot.selectedStage) {
      slot.selectedStage = step.module;
    }

    for (const t of slot.liveTests) {
      t.expanded = (t.name === step.name && t.module === step.module);
    }
    slot.liveTests = slot.liveTests;

    setTimeout(() => this._scrollToTest(step.name, step.module, 10), 50);
  }

  /** Scroll test list panel so the target test is visible. */
  private _scrollToTest(name: string, module: string | null, attempts: number): void {
    const tryScroll = (remaining: number) => {
      const el = document.querySelector(
        `[data-test-name="${name}"][data-test-module="${module}"]`
      ) as HTMLElement;
      if (el) {
        let panel: HTMLElement | null = el.parentElement;
        while (panel && panel.scrollHeight <= panel.clientHeight) {
          panel = panel.parentElement;
        }
        if (panel) {
          let offset = 0;
          let node: HTMLElement | null = el;
          while (node && node !== panel) {
            offset += node.offsetTop;
            node = node.offsetParent as HTMLElement | null;
            if (node && !panel.contains(node)) break;
          }
          panel.scrollTop = offset;
        } else {
          el.scrollIntoView({ block: 'start' });
        }
      } else if (remaining > 0) {
        setTimeout(() => tryScroll(remaining - 1), 50);
      }
    };
    tryScroll(attempts);
  }
}

// ── Svelte context helpers ────────────────────────────────────────────

const RUN_EXEC_CTX_KEY = Symbol('run-execution-context');

export function createRunExecutionContext(config: RunExecutionConfig): RunExecutionContext {
  const ctx = new RunExecutionContext(config);
  setContext(RUN_EXEC_CTX_KEY, ctx);
  return ctx;
}

export function getRunExecutionContext(): RunExecutionContext {
  return getContext<RunExecutionContext>(RUN_EXEC_CTX_KEY);
}
