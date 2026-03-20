/**
 * Comprehensive tests for RunContext class.
 *
 * RunContext manages all state for a validation run detail page:
 * live test timeline, UART buffering, telemetry, stage derivation,
 * analysis mode, and auto-follow behavior.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flushPromises } from '../../../tests/helpers';

// ── Module mocks (must be declared before imports) ──────────────────

vi.mock('svelte', () => ({
  getContext: vi.fn(),
  setContext: vi.fn(),
}));

vi.mock('$lib/api', () => ({
  apiFetch: vi.fn(),
  api: { post: vi.fn(), get: vi.fn() },
  getToken: vi.fn(() => 'mock-token'),
}));

vi.mock('$lib/services/websocket', () => ({
  subscribeValidationRunWithLogs: vi.fn(() => vi.fn()),
}));

// ── Imports under test ──────────────────────────────────────────────

import { RunContext } from './run-context.svelte';
import { apiFetch, api, getToken } from '$lib/api';
import { subscribeValidationRunWithLogs } from '$lib/services/websocket';
import type { LiveTest, BuildJob, Stage } from './run-context.svelte';

// ── Helpers ─────────────────────────────────────────────────────────

function makeTest(overrides: Partial<LiveTest> = {}): LiveTest {
  return {
    name: 'test_boot',
    module: 'power',
    status: 'queued',
    durationS: null,
    startedAtMs: null,
    errorMessage: null,
    measurements: null,
    logOutput: null,
    expanded: false,
    ...overrides,
  };
}

function makeBuildJob(overrides: Partial<BuildJob> = {}): BuildJob {
  return {
    id: 'build-1',
    product: 'alpha',
    fwType: 'app',
    variant: 'b0',
    status: 'SUCCESS',
    commitSha: 'abc123',
    branch: 'main',
    logOutput: null,
    errorMessage: null,
    durationSeconds: 42,
    expanded: false,
    ...overrides,
  };
}

function makeRun(overrides: Record<string, unknown> = {}) {
  return {
    id: 'run-1',
    name: 'Test Run',
    productId: 'prod-1',
    fixtureId: null,
    status: 'ACTIVE',
    config: null,
    targetCount: 5,
    completedCount: 2,
    passedCount: 2,
    failedCount: 0,
    startedAt: '2026-03-20T10:00:00Z',
    finishedAt: null,
    notes: null,
    createdAt: '2026-03-20T09:59:00Z',
    updatedAt: '2026-03-20T10:00:00Z',
    ...overrides,
  };
}

// ── Tests ───────────────────────────────────────────────────────────

describe('RunContext', () => {
  let ctx: RunContext;

  beforeEach(() => {
    vi.clearAllMocks();
    ctx = new RunContext('run-123');
  });

  afterEach(() => {
    // destroy() must be called while timers are still available
    // (before vi.useRealTimers() in nested blocks)
    try { ctx.destroy(); } catch { /* safe teardown */ }
  });

  // ================================================================
  // 1. State initialization
  // ================================================================

  describe('state initialization', () => {
    it('sets runId correctly', () => {
      expect(ctx.runId).toBe('run-123');
    });

    it('allows runId to be changed via setter', () => {
      ctx.runId = 'run-456';
      expect(ctx.runId).toBe('run-456');
    });

    it('defaults run to null', () => {
      expect(ctx.run).toBeNull();
    });

    it('defaults loading to true', () => {
      expect(ctx.loading).toBe(true);
    });

    it('defaults error to null', () => {
      expect(ctx.error).toBeNull();
    });

    it('defaults liveTests to empty array', () => {
      expect(ctx.liveTests).toEqual([]);
    });

    it('defaults liveRunning to false', () => {
      expect(ctx.liveRunning).toBe(false);
    });

    it('defaults liveFinished to false', () => {
      expect(ctx.liveFinished).toBe(false);
    });

    it('defaults liveSummary to null', () => {
      expect(ctx.liveSummary).toBeNull();
    });

    it('defaults autoFollow to true', () => {
      expect(ctx.autoFollow).toBe(true);
    });

    it('defaults selectedStage to null', () => {
      expect(ctx.selectedStage).toBeNull();
    });

    it('defaults selectedRange to null', () => {
      expect(ctx.selectedRange).toBeNull();
    });

    it('defaults telemetryManifest to null', () => {
      expect(ctx.telemetryManifest).toBeNull();
    });

    it('defaults cancel-related state', () => {
      expect(ctx.cancelling).toBe(false);
      expect(ctx.confirmCancel).toBe(false);
      expect(ctx.cancelConfirmText).toBe('');
    });

    it('defaults trigger-related state', () => {
      expect(ctx.triggering).toBe(false);
      expect(ctx.showTrigger).toBe(false);
      expect(ctx.triggerFwVersion).toBe('');
    });

    it('defaults power and UART arrays to empty', () => {
      expect(ctx.powerSamples).toEqual([]);
      expect(ctx.powerChgSamples).toEqual([]);
      expect(ctx.uartAppLines).toEqual([]);
      expect(ctx.uartCommsLines).toEqual([]);
    });

    it('defaults artifacts to empty', () => {
      expect(ctx.artifacts).toEqual([]);
      expect(ctx.artifactsLoading).toBe(false);
    });

    it('defaults buildJobs to empty', () => {
      expect(ctx.buildJobs).toEqual([]);
    });

    it('defaults layout/resize state', () => {
      expect(ctx.bottomPanelCollapsed).toBe(false);
      expect(ctx.topPanelHeight).toBe(50);
      expect(ctx.resizing).toBe(false);
      expect(ctx.sidebarWidth).toBe(192);
      expect(ctx.chartsWidth).toBe(576);
      expect(ctx.vResizing).toBeNull();
    });

    it('defaults historical telemetry state', () => {
      expect(ctx.historicalPower).toEqual([]);
      expect(ctx.historicalPowerChg).toEqual([]);
      expect(ctx.historicalUartAppTs).toEqual([]);
      expect(ctx.historicalUartCommsTs).toEqual([]);
      expect(ctx.telemetryLoading).toBe(false);
    });
  });

  // ================================================================
  // 2. Stage derivation
  // ================================================================

  describe('stage derivation', () => {
    it('returns empty stages when no tests and no build jobs', () => {
      expect(ctx.stages).toEqual([]);
    });

    it('groups tests by module into separate stages', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_boot', module: 'power', status: 'passed', durationS: 1.5 }),
        makeTest({ name: 'test_current', module: 'power', status: 'running' }),
        makeTest({ name: 'test_uart', module: 'comms', status: 'queued' }),
      ];

      const stages = ctx.stages;
      expect(stages).toHaveLength(2);

      const commsStage = stages.find(s => s.name === 'comms')!;
      expect(commsStage).toBeDefined();
      expect(commsStage.type).toBe('test');
      expect(commsStage.tests).toHaveLength(1);

      const powerStage = stages.find(s => s.name === 'power')!;
      expect(powerStage).toBeDefined();
      expect(powerStage.type).toBe('test');
      expect(powerStage.tests).toHaveLength(2);
      expect(powerStage.passed).toBe(1);
      expect(powerStage.running).toBe(1);
      expect(powerStage.durationS).toBe(1.5);
    });

    it('uses "Tests" as stage name when module is null', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_solo', module: null }),
      ];

      const stages = ctx.stages;
      expect(stages).toHaveLength(1);
      expect(stages[0].name).toBe('Tests');
    });

    it('sorts test stages alphabetically', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_z', module: 'zeta' }),
        makeTest({ name: 'test_a', module: 'alpha' }),
        makeTest({ name: 'test_m', module: 'mid' }),
      ];

      const stages = ctx.stages;
      expect(stages.map(s => s.name)).toEqual(['alpha', 'mid', 'zeta']);
    });

    it('creates a Build stage from build jobs', () => {
      ctx.buildJobs = [
        makeBuildJob({ status: 'SUCCESS', durationSeconds: 30 }),
        makeBuildJob({ id: 'build-2', status: 'FAILED', durationSeconds: 10 }),
        makeBuildJob({ id: 'build-3', status: 'BUILDING', durationSeconds: null }),
      ];

      const stages = ctx.stages;
      expect(stages).toHaveLength(1);

      const buildStage = stages[0];
      expect(buildStage.name).toBe('Build');
      expect(buildStage.type).toBe('build');
      expect(buildStage.builds).toHaveLength(3);
      expect(buildStage.passed).toBe(1);
      expect(buildStage.failed).toBe(1);
      expect(buildStage.running).toBe(1);
      expect(buildStage.skipped).toBe(0);
      expect(buildStage.durationS).toBe(40);
      expect(buildStage.tests).toEqual([]);
    });

    it('places Build stage before test stages', () => {
      ctx.buildJobs = [makeBuildJob()];
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'alpha' }),
      ];

      const stages = ctx.stages;
      expect(stages).toHaveLength(2);
      expect(stages[0].name).toBe('Build');
      expect(stages[1].name).toBe('alpha');
    });

    it('correctly tallies passed/failed/skipped/running counts', () => {
      ctx.liveTests = [
        makeTest({ name: 't1', module: 'mod', status: 'passed', durationS: 1 }),
        makeTest({ name: 't2', module: 'mod', status: 'passed', durationS: 2 }),
        makeTest({ name: 't3', module: 'mod', status: 'failed', durationS: 3 }),
        makeTest({ name: 't4', module: 'mod', status: 'skipped' }),
        makeTest({ name: 't5', module: 'mod', status: 'running' }),
        makeTest({ name: 't6', module: 'mod', status: 'queued' }),
      ];

      const stage = ctx.stages[0];
      expect(stage.passed).toBe(2);
      expect(stage.failed).toBe(1);
      expect(stage.skipped).toBe(1);
      expect(stage.running).toBe(1);
      expect(stage.durationS).toBe(6);
    });
  });

  // ================================================================
  // 3. Live test management (WebSocket handlers)
  // ================================================================

  describe('live test management', () => {
    let wsCallbacks: Record<string, Function>;

    beforeEach(() => {
      // Capture the WebSocket callbacks when subscribe is called
      vi.mocked(subscribeValidationRunWithLogs).mockImplementation(
        (_runId: string, callbacks: any) => {
          wsCallbacks = callbacks;
          return vi.fn();
        }
      );
      vi.mocked(apiFetch).mockImplementation(async (url: string) => {
        if (url.includes('/artifacts')) return { data: [] };
        return { data: makeRun() };
      });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ data: [] }),
        text: vi.fn().mockResolvedValue(''),
      });
      ctx.subscribe();
    });

    describe('onTestStart', () => {
      it('creates a new test entry with status running', () => {
        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          executionId: 'ex-1',
        });

        const test = ctx.findTest('test_boot', 'power');
        expect(test).toBeDefined();
        expect(test!.status).toBe('running');
        expect(test!.startedAtMs).toBeGreaterThan(0);
      });

      it('sets liveRunning to true', () => {
        expect(ctx.liveRunning).toBe(false);
        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_x',
          module: 'mod',
          executionId: 'ex-1',
        });
        expect(ctx.liveRunning).toBe(true);
      });

      it('updates existing queued test to running on start', () => {
        ctx.liveTests = [makeTest({ name: 'test_boot', module: 'power', status: 'queued' })];

        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          executionId: 'ex-1',
        });

        expect(ctx.liveTests).toHaveLength(1);
        expect(ctx.liveTests[0].status).toBe('running');
      });

      it('auto-selects the stage matching the test module', () => {
        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          executionId: 'ex-1',
        });

        expect(ctx.selectedStage).toBe('power');
      });

      it('with autoFollow=true, expands starting test and collapses others', () => {
        ctx.liveTests = [
          makeTest({ name: 'test_a', module: 'mod', status: 'passed', expanded: true }),
        ];
        ctx.autoFollow = true;

        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_b',
          module: 'mod',
          executionId: 'ex-2',
        });

        const testA = ctx.findTest('test_a', 'mod');
        const testB = ctx.findTest('test_b', 'mod');
        expect(testA!.expanded).toBe(false);
        expect(testB!.expanded).toBe(true);
      });

      it('with autoFollow=false, does not change expansion', () => {
        ctx.autoFollow = false;
        ctx.liveTests = [
          makeTest({ name: 'test_a', module: 'mod', status: 'passed', expanded: true }),
        ];

        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_b',
          module: 'mod',
          executionId: 'ex-2',
        });

        const testA = ctx.findTest('test_a', 'mod');
        expect(testA!.expanded).toBe(true);
      });

      it('does not change selectedStage if module matches current', () => {
        ctx.selectedStage = 'power';

        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          executionId: 'ex-1',
        });

        expect(ctx.selectedStage).toBe('power');
      });

      it('switches selectedStage when module changes', () => {
        ctx.selectedStage = 'power';

        wsCallbacks.onTestStart({
          runId: 'run-123',
          testName: 'test_uart',
          module: 'comms',
          executionId: 'ex-2',
        });

        expect(ctx.selectedStage).toBe('comms');
      });
    });

    describe('onTestResult', () => {
      beforeEach(() => {
        ctx.liveTests = [
          makeTest({ name: 'test_boot', module: 'power', status: 'running', expanded: true }),
          makeTest({ name: 'test_current', module: 'power', status: 'queued' }),
          makeTest({ name: 'test_sleep', module: 'power', status: 'queued' }),
        ];
      });

      it('updates test status to passed on success', () => {
        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          passed: true,
          durationS: 3.5,
          errorMessage: null,
          measurements: { current_mA: 33 },
          logOutput: 'Boot OK',
        });

        const test = ctx.findTest('test_boot', 'power');
        expect(test!.status).toBe('passed');
        expect(test!.durationS).toBe(3.5);
        expect(test!.measurements).toEqual({ current_mA: 33 });
        expect(test!.logOutput).toBe('Boot OK');
      });

      it('collapses passed test when autoFollow is enabled', () => {
        ctx.autoFollow = true;

        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          passed: true,
          durationS: 2.0,
          errorMessage: null,
          measurements: null,
          logOutput: null,
        });

        expect(ctx.findTest('test_boot', 'power')!.expanded).toBe(false);
      });

      it('updates test status to failed on failure', () => {
        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          passed: false,
          durationS: 1.2,
          errorMessage: 'Current too low: 0.5mA',
          measurements: null,
          logOutput: 'Error log',
        });

        const test = ctx.findTest('test_boot', 'power');
        expect(test!.status).toBe('failed');
        expect(test!.errorMessage).toBe('Current too low: 0.5mA');
      });

      it('keeps failed test expanded', () => {
        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          passed: false,
          durationS: 1.0,
          errorMessage: 'failed',
          measurements: null,
          logOutput: null,
        });

        expect(ctx.findTest('test_boot', 'power')!.expanded).toBe(true);
      });

      it('marks remaining queued/running tests in same module as skipped on failure', () => {
        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          passed: false,
          durationS: 1.0,
          errorMessage: 'failed',
          measurements: null,
          logOutput: null,
        });

        expect(ctx.findTest('test_current', 'power')!.status).toBe('skipped');
        expect(ctx.findTest('test_sleep', 'power')!.status).toBe('skipped');
      });

      it('does not skip tests in a different module on failure', () => {
        ctx.liveTests.push(
          makeTest({ name: 'test_uart', module: 'comms', status: 'queued' })
        );

        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          passed: false,
          durationS: 1.0,
          errorMessage: 'failed',
          measurements: null,
          logOutput: null,
        });

        expect(ctx.findTest('test_uart', 'comms')!.status).toBe('queued');
      });

      it('updates test status to skipped when skipped flag is set', () => {
        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'test_boot',
          module: 'power',
          passed: false,
          skipped: true,
          durationS: null,
          errorMessage: null,
          measurements: null,
          logOutput: null,
        });

        expect(ctx.findTest('test_boot', 'power')!.status).toBe('skipped');
      });

      it('does nothing when test name is not found', () => {
        const testsBefore = [...ctx.liveTests];

        wsCallbacks.onTestResult({
          runId: 'run-123',
          testName: 'nonexistent_test',
          module: 'power',
          passed: true,
          durationS: 1,
          errorMessage: null,
          measurements: null,
          logOutput: null,
        });

        expect(ctx.liveTests).toHaveLength(testsBefore.length);
      });
    });

    describe('onRunFinish', () => {
      it('sets liveRunning=false and liveFinished=true', () => {
        ctx.liveRunning = true;

        wsCallbacks.onRunFinish({
          runId: 'run-123',
          status: 'COMPLETED',
          total: 5,
          passed: 4,
          failed: 1,
          errors: 0,
          durationS: 120,
        });

        expect(ctx.liveRunning).toBe(false);
        expect(ctx.liveFinished).toBe(true);
      });

      it('populates liveSummary from finish event', () => {
        wsCallbacks.onRunFinish({
          runId: 'run-123',
          status: 'COMPLETED',
          total: 10,
          passed: 8,
          failed: 1,
          errors: 1,
          durationS: 300,
        });

        expect(ctx.liveSummary).toEqual({
          total: 10,
          passed: 8,
          failed: 1,
          errors: 1,
          durationS: 300,
        });
      });

      it('clears simulating flag', () => {
        ctx.simulating = true;

        wsCallbacks.onRunFinish({
          runId: 'run-123',
          status: 'COMPLETED',
          total: 1,
          passed: 1,
          failed: 0,
          errors: 0,
          durationS: 10,
        });

        expect(ctx.simulating).toBe(false);
      });
    });

    describe('onTestList', () => {
      it('populates liveTests from test list when list is empty', () => {
        ctx.liveTests = [];

        wsCallbacks.onTestList({
          runId: 'run-123',
          tests: [
            { name: 'test_a', module: 'mod_a' },
            { name: 'test_b', module: 'mod_b' },
          ],
        });

        expect(ctx.liveTests).toHaveLength(2);
        expect(ctx.liveTests[0].status).toBe('queued');
        expect(ctx.liveTests[1].status).toBe('queued');
      });

      it('sorts test list alphabetically by name', () => {
        wsCallbacks.onTestList({
          runId: 'run-123',
          tests: [
            { name: 'test_z', module: 'mod' },
            { name: 'test_a', module: 'mod' },
          ],
        });

        expect(ctx.liveTests[0].name).toBe('test_a');
        expect(ctx.liveTests[1].name).toBe('test_z');
      });

      it('does not overwrite tests when some are already running', () => {
        ctx.liveTests = [
          makeTest({ name: 'test_a', module: 'mod', status: 'running' }),
        ];

        wsCallbacks.onTestList({
          runId: 'run-123',
          tests: [
            { name: 'test_x', module: 'mod' },
            { name: 'test_y', module: 'mod' },
          ],
        });

        // Should keep existing tests since one is running (not all queued)
        expect(ctx.liveTests).toHaveLength(1);
        expect(ctx.liveTests[0].name).toBe('test_a');
      });

      it('replaces test list when all existing are queued', () => {
        ctx.liveTests = [
          makeTest({ name: 'test_old', module: 'mod', status: 'queued' }),
        ];

        wsCallbacks.onTestList({
          runId: 'run-123',
          tests: [
            { name: 'test_new_a', module: 'mod' },
            { name: 'test_new_b', module: 'mod' },
          ],
        });

        expect(ctx.liveTests).toHaveLength(2);
        expect(ctx.liveTests[0].name).toBe('test_new_a');
      });
    });
  });

  // ================================================================
  // 4. UART buffering
  // ================================================================

  describe('UART buffering', () => {
    let wsCallbacks: Record<string, Function>;

    beforeEach(() => {
      vi.useFakeTimers();

      vi.mocked(subscribeValidationRunWithLogs).mockImplementation(
        (_runId: string, callbacks: any) => {
          wsCallbacks = callbacks;
          return vi.fn();
        }
      );
      vi.mocked(apiFetch).mockImplementation(async (url: string) => {
        if (url.includes('/artifacts')) return { data: [] };
        return { data: makeRun() };
      });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ data: [] }),
        text: vi.fn().mockResolvedValue(''),
      });
      ctx.subscribe();
    });

    afterEach(() => {
      ctx.destroy();
      vi.useRealTimers();
    });

    it('batches UART lines and flushes after 200ms', () => {
      wsCallbacks.onTelemetry({
        runId: 'run-123',
        samples: [
          { t: 1, type: 'uart', target: 'app', line: 'line1' },
          { t: 2, type: 'uart', target: 'app', line: 'line2' },
        ],
      });

      // Before flush, lines should still be empty (pending)
      expect(ctx.uartAppLines).toEqual([]);

      // Advance past the 200ms flush timer
      vi.advanceTimersByTime(200);

      expect(ctx.uartAppLines).toHaveLength(2);
    });

    it('separates app and comms UART lines', () => {
      wsCallbacks.onTelemetry({
        runId: 'run-123',
        samples: [
          { t: 1, type: 'uart', target: 'app', line: 'app line' },
          { t: 2, type: 'uart', target: 'comms', line: 'comms line' },
        ],
      });

      vi.advanceTimersByTime(200);

      expect(ctx.uartAppLines).toHaveLength(1);
      expect(ctx.uartCommsLines).toHaveLength(1);
    });

    it('caps UART lines at MAX_UART_LINES (1500)', () => {
      // Pre-fill with 1490 lines
      const preLines: string[] = [];
      for (let i = 0; i < 1490; i++) {
        preLines.push(`old-line-${i}`);
      }
      ctx.uartAppLines = preLines;

      // Add 20 more via telemetry (total would be 1510, capped to 1500)
      const samples = [];
      for (let i = 0; i < 20; i++) {
        samples.push({ t: i, type: 'uart', target: 'app', line: `new-${i}` });
      }
      wsCallbacks.onTelemetry({ runId: 'run-123', samples });

      vi.advanceTimersByTime(200);

      expect(ctx.uartAppLines).toHaveLength(1500);
      // Oldest lines should have been trimmed
      expect(ctx.uartAppLines[0]).toContain('old-line-');
      expect(ctx.uartAppLines[ctx.uartAppLines.length - 1]).toContain('new-19');
    });

    it('batches multiple telemetry pushes into a single flush', () => {
      wsCallbacks.onTelemetry({
        runId: 'run-123',
        samples: [{ t: 1, type: 'uart', target: 'app', line: 'first' }],
      });
      wsCallbacks.onTelemetry({
        runId: 'run-123',
        samples: [{ t: 2, type: 'uart', target: 'app', line: 'second' }],
      });

      // Only one timer should be scheduled
      vi.advanceTimersByTime(200);

      expect(ctx.uartAppLines).toHaveLength(2);
    });

    it('flushes log chunks to the currently running test', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_running', module: 'mod', status: 'running', logOutput: 'existing ' }),
      ];

      wsCallbacks.onLogChunk({
        runId: 'run-123',
        file: 'output.log',
        offset: 0,
        data: btoa('new chunk'),
        timestamp: Date.now(),
      });

      vi.advanceTimersByTime(200);

      const running = ctx.findTest('test_running', 'mod');
      expect(running!.logOutput).toBe('existing new chunk');
    });
  });

  // ================================================================
  // 5. Analysis mode
  // ================================================================

  describe('analysis mode', () => {
    it('is false when run is ACTIVE', () => {
      ctx.run = makeRun({ status: 'ACTIVE' }) as any;
      ctx.telemetryManifest = { version: 1, runId: 'run-1', startedAt: null, finishedAt: null, totalSamples: 0, channels: {}, steps: [] };

      expect(ctx.analysisMode).toBe(false);
    });

    it('is false when run is completed but no telemetry manifest', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = null;

      expect(ctx.analysisMode).toBe(false);
    });

    it('is true when run is completed AND telemetry manifest exists', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = { version: 1, runId: 'run-1', startedAt: null, finishedAt: null, totalSamples: 100, channels: {}, steps: [] };

      expect(ctx.analysisMode).toBe(true);
    });

    it('is true when run is CANCELLED and manifest exists', () => {
      ctx.run = makeRun({ status: 'CANCELLED' }) as any;
      ctx.telemetryManifest = { version: 1, runId: 'run-1', startedAt: null, finishedAt: null, totalSamples: 0, channels: {}, steps: [] };

      expect(ctx.analysisMode).toBe(true);
    });
  });

  // ================================================================
  // 6. Data filtering (selectedRange, effectivePower, effectiveUart)
  // ================================================================

  describe('data filtering', () => {
    describe('filteredPower', () => {
      it('returns all historical power when selectedRange is null', () => {
        ctx.historicalPower = [
          { t: 100, mA: 10, mV: 3300 },
          { t: 200, mA: 20, mV: 3300 },
        ];
        ctx.selectedRange = null;

        expect(ctx.filteredPower).toEqual(ctx.historicalPower);
      });

      it('filters historical power by selectedRange', () => {
        ctx.historicalPower = [
          { t: 100, mA: 10, mV: 3300 },
          { t: 150, mA: 15, mV: 3300 },
          { t: 200, mA: 20, mV: 3300 },
          { t: 250, mA: 25, mV: 3300 },
        ];
        ctx.selectedRange = { start: 140, end: 210 };

        expect(ctx.filteredPower).toHaveLength(2);
        expect(ctx.filteredPower[0].t).toBe(150);
        expect(ctx.filteredPower[1].t).toBe(200);
      });
    });

    describe('filteredPowerChg', () => {
      it('returns all historical power_chg when selectedRange is null', () => {
        ctx.historicalPowerChg = [
          { t: 100, mA: 5, mV: 5000 },
        ];
        ctx.selectedRange = null;

        expect(ctx.filteredPowerChg).toEqual(ctx.historicalPowerChg);
      });

      it('filters historical power_chg by selectedRange', () => {
        ctx.historicalPowerChg = [
          { t: 50, mA: 5, mV: 5000 },
          { t: 100, mA: 10, mV: 5000 },
          { t: 150, mA: 15, mV: 5000 },
        ];
        ctx.selectedRange = { start: 90, end: 110 };

        expect(ctx.filteredPowerChg).toHaveLength(1);
        expect(ctx.filteredPowerChg[0].t).toBe(100);
      });
    });

    describe('filteredUartApp', () => {
      it('returns all historical UART when selectedRange is null', () => {
        ctx.historicalUartAppTs = [
          { t: 100, line: 'line A' },
          { t: 200, line: 'line B' },
        ];
        ctx.selectedRange = null;

        expect(ctx.filteredUartApp).toEqual(['line A', 'line B']);
      });

      it('filters historical UART by selectedRange', () => {
        ctx.historicalUartAppTs = [
          { t: 100, line: 'early' },
          { t: 200, line: 'middle' },
          { t: 300, line: 'late' },
        ];
        ctx.selectedRange = { start: 150, end: 250 };

        expect(ctx.filteredUartApp).toEqual(['middle']);
      });

      it('returns empty array when range excludes all historical lines', () => {
        ctx.historicalUartAppTs = [
          { t: 100, line: 'only line' },
        ];
        ctx.selectedRange = { start: 500, end: 600 };

        // historicalUartAppTs is non-empty so it filters, resulting in empty
        expect(ctx.filteredUartApp).toEqual([]);
      });

      it('returns all historicalUartApp when historicalUartAppTs is empty (no filter applied)', () => {
        ctx.historicalUartAppTs = [];
        ctx.selectedRange = { start: 100, end: 200 };

        // When historicalUartAppTs is empty, returns historicalUartApp (also empty)
        expect(ctx.filteredUartApp).toEqual([]);
      });

      it('returns empty when both historical and filtered are empty', () => {
        ctx.historicalUartAppTs = [];
        ctx.selectedRange = { start: 100, end: 200 };

        expect(ctx.filteredUartApp).toEqual([]);
      });
    });

    describe('filteredUartComms', () => {
      it('filters comms UART lines by selectedRange', () => {
        ctx.historicalUartCommsTs = [
          { t: 100, line: 'comms-a' },
          { t: 200, line: 'comms-b' },
          { t: 300, line: 'comms-c' },
        ];
        ctx.selectedRange = { start: 190, end: 310 };

        expect(ctx.filteredUartComms).toEqual(['comms-b', 'comms-c']);
      });
    });

    describe('effectivePower', () => {
      it('returns live powerSamples when not in analysisMode', () => {
        ctx.run = makeRun({ status: 'ACTIVE' }) as any;
        ctx.telemetryManifest = null;
        ctx.powerSamples = [{ t: 1, mA: 33, mV: 4500 }];
        ctx.historicalPower = [{ t: 2, mA: 44, mV: 4500 }];

        expect(ctx.effectivePower).toEqual([{ t: 1, mA: 33, mV: 4500 }]);
      });

      it('returns filtered historical power when in analysisMode with selectedRange', () => {
        ctx.run = makeRun({ status: 'COMPLETED' }) as any;
        ctx.telemetryManifest = { version: 1, runId: 'r', startedAt: null, finishedAt: null, totalSamples: 0, channels: {}, steps: [] };
        ctx.historicalPower = [
          { t: 100, mA: 10, mV: 3300 },
          { t: 200, mA: 20, mV: 3300 },
        ];
        ctx.selectedRange = { start: 150, end: 250 };

        expect(ctx.effectivePower).toEqual([{ t: 200, mA: 20, mV: 3300 }]);
      });

      it('returns all historical power when in analysisMode with no selectedRange', () => {
        ctx.run = makeRun({ status: 'COMPLETED' }) as any;
        ctx.telemetryManifest = { version: 1, runId: 'r', startedAt: null, finishedAt: null, totalSamples: 0, channels: {}, steps: [] };
        ctx.historicalPower = [
          { t: 100, mA: 10, mV: 3300 },
          { t: 200, mA: 20, mV: 3300 },
        ];
        ctx.selectedRange = null;

        expect(ctx.effectivePower).toEqual(ctx.historicalPower);
      });
    });

    describe('effectivePowerChg', () => {
      it('returns live powerChgSamples when not in analysisMode', () => {
        ctx.run = makeRun({ status: 'ACTIVE' }) as any;
        ctx.powerChgSamples = [{ t: 1, mA: 5, mV: 5000 }];

        expect(ctx.effectivePowerChg).toEqual([{ t: 1, mA: 5, mV: 5000 }]);
      });
    });

    describe('effectiveUartApp', () => {
      it('returns live uartAppLines when not in analysisMode', () => {
        ctx.run = makeRun({ status: 'ACTIVE' }) as any;
        ctx.uartAppLines = ['live line 1', 'live line 2'];

        expect(ctx.effectiveUartApp).toEqual(['live line 1', 'live line 2']);
      });

      it('returns filtered historical UART in analysisMode with range', () => {
        ctx.run = makeRun({ status: 'COMPLETED' }) as any;
        ctx.telemetryManifest = { version: 1, runId: 'r', startedAt: null, finishedAt: null, totalSamples: 0, channels: {}, steps: [] };
        ctx.historicalUartAppTs = [
          { t: 100, line: 'early' },
          { t: 200, line: 'targeted' },
          { t: 300, line: 'late' },
        ];
        ctx.selectedRange = { start: 150, end: 250 };

        expect(ctx.effectiveUartApp).toEqual(['targeted']);
      });

      it('falls back to live uartAppLines when filtered historical is empty in analysisMode', () => {
        ctx.run = makeRun({ status: 'COMPLETED' }) as any;
        ctx.telemetryManifest = { version: 1, runId: 'r', startedAt: null, finishedAt: null, totalSamples: 0, channels: {}, steps: [] };
        ctx.historicalUartAppTs = [];
        ctx.uartAppLines = ['live fallback'];
        ctx.selectedRange = { start: 100, end: 200 };

        expect(ctx.effectiveUartApp).toEqual(['live fallback']);
      });
    });

    describe('effectiveUartComms', () => {
      it('returns live uartCommsLines when not in analysisMode', () => {
        ctx.run = makeRun({ status: 'ACTIVE' }) as any;
        ctx.uartCommsLines = ['comms live'];

        expect(ctx.effectiveUartComms).toEqual(['comms live']);
      });

      it('falls back to live comms lines when filtered historical is empty', () => {
        ctx.run = makeRun({ status: 'COMPLETED' }) as any;
        ctx.telemetryManifest = { version: 1, runId: 'r', startedAt: null, finishedAt: null, totalSamples: 0, channels: {}, steps: [] };
        ctx.historicalUartCommsTs = [];
        ctx.uartCommsLines = ['comms fallback'];
        ctx.selectedRange = { start: 100, end: 200 };

        expect(ctx.effectiveUartComms).toEqual(['comms fallback']);
      });
    });
  });

  // ================================================================
  // 7. Test expansion / auto-follow
  // ================================================================

  describe('test expansion and auto-follow', () => {
    it('toggleTestExpanded toggles the expanded flag', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod', expanded: false }),
      ];

      ctx.toggleTestExpanded('test_a', 'mod');
      expect(ctx.findTest('test_a', 'mod')!.expanded).toBe(true);

      ctx.toggleTestExpanded('test_a', 'mod');
      expect(ctx.findTest('test_a', 'mod')!.expanded).toBe(false);
    });

    it('does nothing when test name not found', () => {
      ctx.liveTests = [makeTest({ name: 'test_a', module: 'mod' })];
      ctx.toggleTestExpanded('nonexistent', 'mod');
      // No error thrown, state unchanged
      expect(ctx.liveTests).toHaveLength(1);
    });

    it('re-enables autoFollow when expanding a running test', () => {
      ctx.autoFollow = false;
      ctx.liveTests = [
        makeTest({ name: 'test_run', module: 'mod', status: 'running', expanded: false }),
      ];

      ctx.toggleTestExpanded('test_run', 'mod');

      expect(ctx.autoFollow).toBe(true);
      expect(ctx.findTest('test_run', 'mod')!.expanded).toBe(true);
    });

    it('disables autoFollow when collapsing a running test', () => {
      ctx.autoFollow = true;
      ctx.liveTests = [
        makeTest({ name: 'test_run', module: 'mod', status: 'running', expanded: true }),
      ];

      ctx.toggleTestExpanded('test_run', 'mod');

      expect(ctx.autoFollow).toBe(false);
      expect(ctx.findTest('test_run', 'mod')!.expanded).toBe(false);
    });

    it('disables autoFollow when clicking a non-running test (expand)', () => {
      ctx.autoFollow = true;
      ctx.liveTests = [
        makeTest({ name: 'test_done', module: 'mod', status: 'passed', expanded: false }),
      ];

      ctx.toggleTestExpanded('test_done', 'mod');

      expect(ctx.autoFollow).toBe(false);
    });

    it('disables autoFollow when clicking a non-running test (collapse)', () => {
      ctx.autoFollow = true;
      ctx.liveTests = [
        makeTest({ name: 'test_done', module: 'mod', status: 'failed', expanded: true }),
      ];

      ctx.toggleTestExpanded('test_done', 'mod');

      expect(ctx.autoFollow).toBe(false);
    });

    it('sets selectedRange when expanding a test in analysisMode with manifest step', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = {
        version: 1,
        runId: 'r',
        startedAt: null,
        finishedAt: null,
        totalSamples: 0,
        channels: {},
        steps: [
          { name: 'test_a', module: 'mod', startedAt: 100, finishedAt: 200 },
        ],
      };
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod', status: 'passed', expanded: false }),
      ];

      ctx.toggleTestExpanded('test_a', 'mod');

      expect(ctx.selectedRange).toEqual({ start: 100, end: 200 });
    });

    it('clears selectedRange when collapsing a test in analysisMode', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = {
        version: 1,
        runId: 'r',
        startedAt: null,
        finishedAt: null,
        totalSamples: 0,
        channels: {},
        steps: [],
      };
      ctx.selectedRange = { start: 100, end: 200 };
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod', status: 'passed', expanded: true }),
      ];

      ctx.toggleTestExpanded('test_a', 'mod');

      expect(ctx.selectedRange).toBeNull();
    });

    it('finds test by name only when module is not provided', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod', expanded: false }),
      ];

      ctx.toggleTestExpanded('test_a');
      expect(ctx.findTest('test_a')!.expanded).toBe(true);
    });

    it('finds test with matching module when module is specified', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod_x', expanded: false }),
        makeTest({ name: 'test_a', module: 'mod_y', expanded: false }),
      ];

      ctx.toggleTestExpanded('test_a', 'mod_y');

      expect(ctx.findTest('test_a', 'mod_x')!.expanded).toBe(false);
      expect(ctx.findTest('test_a', 'mod_y')!.expanded).toBe(true);
    });
  });

  // ================================================================
  // 8. findTest helper
  // ================================================================

  describe('findTest', () => {
    it('finds test by name when no module is given', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod_x' }),
        makeTest({ name: 'test_b', module: 'mod_y' }),
      ];

      expect(ctx.findTest('test_a')).toBe(ctx.liveTests[0]);
    });

    it('finds test by name and module', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod_x' }),
        makeTest({ name: 'test_a', module: 'mod_y' }),
      ];

      expect(ctx.findTest('test_a', 'mod_y')).toBe(ctx.liveTests[1]);
    });

    it('returns undefined when test is not found', () => {
      ctx.liveTests = [];
      expect(ctx.findTest('nonexistent')).toBeUndefined();
    });

    it('returns undefined when module does not match', () => {
      ctx.liveTests = [
        makeTest({ name: 'test_a', module: 'mod_x' }),
      ];

      expect(ctx.findTest('test_a', 'mod_z')).toBeUndefined();
    });
  });

  // ================================================================
  // 9. Derived counts
  // ================================================================

  describe('derived live counts', () => {
    beforeEach(() => {
      ctx.liveTests = [
        makeTest({ name: 't1', module: 'm', status: 'passed' }),
        makeTest({ name: 't2', module: 'm', status: 'passed' }),
        makeTest({ name: 't3', module: 'm', status: 'failed' }),
        makeTest({ name: 't4', module: 'm', status: 'skipped' }),
        makeTest({ name: 't5', module: 'm', status: 'running' }),
        makeTest({ name: 't6', module: 'm', status: 'queued' }),
      ];
    });

    it('livePassedCount counts passed tests', () => {
      expect(ctx.livePassedCount).toBe(2);
    });

    it('liveFailedCount counts failed tests', () => {
      expect(ctx.liveFailedCount).toBe(1);
    });

    it('liveSkippedCount counts skipped tests', () => {
      expect(ctx.liveSkippedCount).toBe(1);
    });

    it('liveCompletedCount sums passed + failed + skipped', () => {
      expect(ctx.liveCompletedCount).toBe(4);
    });
  });

  // ================================================================
  // 10. progressPct and durationMs
  // ================================================================

  describe('progressPct', () => {
    it('returns 0 when run is null', () => {
      ctx.run = null;
      expect(ctx.progressPct).toBe(0);
    });

    it('returns 0 when targetCount is 0', () => {
      ctx.run = makeRun({ targetCount: 0 }) as any;
      expect(ctx.progressPct).toBe(0);
    });

    it('calculates correct percentage', () => {
      ctx.run = makeRun({ targetCount: 10, completedCount: 3 }) as any;
      expect(ctx.progressPct).toBe(30);
    });

    it('rounds to integer', () => {
      ctx.run = makeRun({ targetCount: 3, completedCount: 1 }) as any;
      expect(ctx.progressPct).toBe(33);
    });
  });

  describe('durationMs', () => {
    it('returns null when run has no startedAt', () => {
      ctx.run = makeRun({ startedAt: null }) as any;
      expect(ctx.durationMs).toBeNull();
    });

    it('calculates duration from startedAt to finishedAt', () => {
      ctx.run = makeRun({
        startedAt: '2026-03-20T10:00:00Z',
        finishedAt: '2026-03-20T10:05:00Z',
      }) as any;

      expect(ctx.durationMs).toBe(5 * 60 * 1000);
    });
  });

  // ================================================================
  // 11. isActive derived
  // ================================================================

  describe('isActive', () => {
    it('returns true when run status is ACTIVE', () => {
      ctx.run = makeRun({ status: 'ACTIVE' }) as any;
      expect(ctx.isActive).toBe(true);
    });

    it('returns false when run status is COMPLETED', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      expect(ctx.isActive).toBe(false);
    });

    it('returns false when run is null', () => {
      ctx.run = null;
      expect(ctx.isActive).toBe(false);
    });
  });

  // ================================================================
  // 12. selectedStageData derived
  // ================================================================

  describe('selectedStageData', () => {
    it('returns null when no stage is selected', () => {
      ctx.liveTests = [makeTest({ name: 't', module: 'mod' })];
      ctx.selectedStage = null;

      expect(ctx.selectedStageData).toBeNull();
    });

    it('returns null when selectedStage does not match any stage', () => {
      ctx.liveTests = [makeTest({ name: 't', module: 'mod' })];
      ctx.selectedStage = 'nonexistent';

      expect(ctx.selectedStageData).toBeNull();
    });

    it('returns the matching stage data', () => {
      ctx.liveTests = [
        makeTest({ name: 'ta', module: 'alpha', status: 'passed' }),
        makeTest({ name: 'tb', module: 'beta' }),
      ];
      ctx.selectedStage = 'alpha';

      const data = ctx.selectedStageData;
      expect(data).not.toBeNull();
      expect(data!.name).toBe('alpha');
      expect(data!.tests).toHaveLength(1);
      expect(data!.passed).toBe(1);
    });
  });

  // ================================================================
  // 13. autoSelectStage
  // ================================================================

  describe('autoSelectStage', () => {
    it('does nothing when no stages exist', () => {
      ctx.autoSelectStage();
      expect(ctx.selectedStage).toBeNull();
    });

    it('does nothing when a stage is already selected', () => {
      ctx.liveTests = [makeTest({ name: 't', module: 'mod' })];
      ctx.selectedStage = 'mod';

      ctx.autoSelectStage();
      expect(ctx.selectedStage).toBe('mod');
    });

    it('selects the stage with running tests first', () => {
      ctx.liveTests = [
        makeTest({ name: 'ta', module: 'alpha', status: 'passed' }),
        makeTest({ name: 'tb', module: 'beta', status: 'running' }),
        makeTest({ name: 'tc', module: 'gamma', status: 'failed' }),
      ];

      ctx.autoSelectStage();
      expect(ctx.selectedStage).toBe('beta');
    });

    it('selects the stage with failed tests if none running', () => {
      ctx.liveTests = [
        makeTest({ name: 'ta', module: 'alpha', status: 'passed' }),
        makeTest({ name: 'tb', module: 'beta', status: 'failed' }),
      ];

      ctx.autoSelectStage();
      expect(ctx.selectedStage).toBe('beta');
    });

    it('selects the first stage when none are running or failed', () => {
      ctx.liveTests = [
        makeTest({ name: 'tb', module: 'beta', status: 'passed' }),
        makeTest({ name: 'ta', module: 'alpha', status: 'passed' }),
      ];

      ctx.autoSelectStage();
      // stages are sorted alphabetically, so 'alpha' is first
      expect(ctx.selectedStage).toBe('alpha');
    });

    it('selects Build stage if it is first and no running/failed test stages', () => {
      ctx.buildJobs = [makeBuildJob({ status: 'SUCCESS' })];
      ctx.liveTests = [];

      ctx.autoSelectStage();
      expect(ctx.selectedStage).toBe('Build');
    });
  });

  // ================================================================
  // 14. Artifact helpers
  // ================================================================

  describe('formatFileSize', () => {
    it('formats bytes', () => {
      expect(ctx.formatFileSize(512)).toBe('512 B');
    });

    it('formats kilobytes', () => {
      expect(ctx.formatFileSize(2048)).toBe('2.0 KB');
    });

    it('formats megabytes', () => {
      expect(ctx.formatFileSize(5 * 1024 * 1024)).toBe('5.0 MB');
    });

    it('handles zero bytes', () => {
      expect(ctx.formatFileSize(0)).toBe('0 B');
    });

    it('handles boundary at 1024', () => {
      expect(ctx.formatFileSize(1024)).toBe('1.0 KB');
    });

    it('handles boundary at 1024*1024', () => {
      expect(ctx.formatFileSize(1024 * 1024)).toBe('1.0 MB');
    });
  });

  describe('isLogFile', () => {
    it('recognizes .log files', () => {
      expect(ctx.isLogFile('output.log')).toBe(true);
    });

    it('recognizes .txt files', () => {
      expect(ctx.isLogFile('notes.txt')).toBe(true);
    });

    it('recognizes .uart files', () => {
      expect(ctx.isLogFile('app_uart.uart')).toBe(true);
    });

    it('recognizes .csv files', () => {
      expect(ctx.isLogFile('data.csv')).toBe(true);
    });

    it('is case insensitive', () => {
      expect(ctx.isLogFile('output.LOG')).toBe(true);
      expect(ctx.isLogFile('output.Txt')).toBe(true);
    });

    it('rejects non-log files', () => {
      expect(ctx.isLogFile('firmware.hex')).toBe(false);
      expect(ctx.isLogFile('image.png')).toBe(false);
      expect(ctx.isLogFile('data.json')).toBe(false);
    });
  });

  // ================================================================
  // 15. runConfig / serialNumber / firmwareVariant / imageTag derived
  // ================================================================

  describe('config-derived fields', () => {
    it('runConfig returns null-ish when run is null', () => {
      ctx.run = null;
      expect(ctx.runConfig).toBeFalsy();
    });

    it('runConfig returns the config object', () => {
      ctx.run = makeRun({ config: { key: 'value' } }) as any;
      expect(ctx.runConfig).toEqual({ key: 'value' });
    });

    it('serialNumber extracts dutSnr from slot config', () => {
      ctx.run = makeRun({
        config: { slot: { dutSnr: '0964' } },
      }) as any;

      expect(ctx.serialNumber).toBe('0964');
    });

    it('serialNumber falls back to serialNumber field', () => {
      ctx.run = makeRun({
        config: { serialNumber: 'SN-001' },
      }) as any;

      expect(ctx.serialNumber).toBe('SN-001');
    });

    it('firmwareVariant extracts from config', () => {
      ctx.run = makeRun({
        config: { firmwareVariant: 'debug' },
      }) as any;

      expect(ctx.firmwareVariant).toBe('debug');
    });

    it('imageTag extracts from trigger in config', () => {
      ctx.run = makeRun({
        config: { trigger: { imageTag: 'staging-v1.0.0' } },
      }) as any;

      expect(ctx.imageTag).toBe('staging-v1.0.0');
    });
  });

  // ================================================================
  // 16. Lifecycle (subscribe / destroy)
  // ================================================================

  describe('lifecycle', () => {
    beforeEach(() => {
      vi.useFakeTimers();
      vi.mocked(apiFetch).mockImplementation(async (url: string) => {
        if (url.includes('/artifacts')) return { data: [] };
        return { data: makeRun() };
      });
      vi.mocked(subscribeValidationRunWithLogs).mockReturnValue(vi.fn());
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ data: [] }),
        text: vi.fn().mockResolvedValue(''),
      });
    });

    afterEach(() => {
      ctx.destroy();
      vi.useRealTimers();
    });

    it('subscribe calls fetchRun, fetchArtifacts, and sets up WebSocket', () => {
      ctx.subscribe();

      expect(apiFetch).toHaveBeenCalledWith('/v2/sessions/run-123');
      expect(subscribeValidationRunWithLogs).toHaveBeenCalledWith(
        'run-123',
        expect.any(Object),
      );
    });

    it('subscribe sets up poll and clock intervals', () => {
      ctx.subscribe();

      // Clock interval updates nowMs every 1s
      const initialNow = ctx.nowMs;
      vi.advanceTimersByTime(1000);
      expect(ctx.nowMs).toBeGreaterThanOrEqual(initialNow);
    });

    it('destroy clears all intervals and timers', () => {
      ctx.subscribe();
      const clearIntervalSpy = vi.spyOn(global, 'clearInterval');
      const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');

      ctx.destroy();

      // Should have cleared poll and clock intervals
      expect(clearIntervalSpy).toHaveBeenCalledTimes(2);
    });

    it('destroy calls WebSocket unsubscribe', () => {
      const unsub = vi.fn();
      vi.mocked(subscribeValidationRunWithLogs).mockReturnValue(unsub);

      ctx.subscribe();
      ctx.destroy();

      expect(unsub).toHaveBeenCalledOnce();
    });

    it('destroy is safe to call multiple times', () => {
      ctx.subscribe();
      ctx.destroy();
      // Second destroy should not throw
      ctx.destroy();
    });
  });

  // ================================================================
  // 17. Telemetry event handling (power samples)
  // ================================================================

  describe('telemetry power handling', () => {
    let wsCallbacks: Record<string, Function>;

    beforeEach(() => {
      vi.useFakeTimers();
      vi.mocked(subscribeValidationRunWithLogs).mockImplementation(
        (_runId: string, callbacks: any) => {
          wsCallbacks = callbacks;
          return vi.fn();
        }
      );
      vi.mocked(apiFetch).mockImplementation(async (url: string) => {
        if (url.includes('/artifacts')) return { data: [] };
        return { data: makeRun() };
      });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ data: [] }),
        text: vi.fn().mockResolvedValue(''),
      });
      ctx.subscribe();
    });

    afterEach(() => {
      ctx.destroy();
      vi.useRealTimers();
    });

    it('appends power samples from telemetry events', () => {
      wsCallbacks.onTelemetry({
        runId: 'run-123',
        samples: [
          { t: 100, type: 'power', mA: 33, mV: 4500 },
          { t: 101, type: 'power', mA: 34, mV: 4500 },
        ],
      });

      expect(ctx.powerSamples).toHaveLength(2);
      expect(ctx.powerSamples[0].mA).toBe(33);
    });

    it('appends power_chg samples separately', () => {
      wsCallbacks.onTelemetry({
        runId: 'run-123',
        samples: [
          { t: 100, type: 'power', mA: 33, mV: 4500 },
          { t: 100, type: 'power_chg', mA: 5, mV: 5000 },
        ],
      });

      expect(ctx.powerSamples).toHaveLength(1);
      expect(ctx.powerChgSamples).toHaveLength(1);
      expect(ctx.powerChgSamples[0].mA).toBe(5);
    });

    it('trims power samples to window when over 120 samples', () => {
      // Pre-fill with 130 samples
      for (let i = 0; i < 130; i++) {
        ctx.powerSamples.push({ t: i, mA: 10, mV: 3300 });
      }

      wsCallbacks.onTelemetry({
        runId: 'run-123',
        samples: [{ t: 200, type: 'power', mA: 50, mV: 4500 }],
      });

      // Should have been trimmed (120 sample cap after cutoff filter)
      expect(ctx.powerSamples.length).toBeLessThanOrEqual(120);
    });
  });

  // ================================================================
  // 18. historicalUartApp / historicalUartComms derived
  // ================================================================

  describe('historicalUartApp/Comms derived', () => {
    it('historicalUartApp maps timestamped lines to plain lines', () => {
      ctx.historicalUartAppTs = [
        { t: 100, line: 'line A' },
        { t: 200, line: 'line B' },
      ];

      expect(ctx.historicalUartApp).toEqual(['line A', 'line B']);
    });

    it('historicalUartComms maps timestamped lines to plain lines', () => {
      ctx.historicalUartCommsTs = [
        { t: 100, line: 'comms A' },
      ];

      expect(ctx.historicalUartComms).toEqual(['comms A']);
    });

    it('returns empty array when no timestamped data', () => {
      expect(ctx.historicalUartApp).toEqual([]);
      expect(ctx.historicalUartComms).toEqual([]);
    });
  });

  // ================================================================
  // 19. handleRangeChange
  // ================================================================

  describe('handleRangeChange', () => {
    it('does nothing when not in analysisMode', () => {
      ctx.run = makeRun({ status: 'ACTIVE' }) as any;
      ctx.telemetryManifest = null;
      ctx.selectedRange = { start: 100, end: 200 };

      ctx.handleRangeChange();

      // No side effects
      expect(ctx.selectedStage).toBeNull();
    });

    it('does nothing when selectedRange is null', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = {
        version: 1, runId: 'r', startedAt: null, finishedAt: null,
        totalSamples: 0, channels: {}, steps: [],
      };
      ctx.selectedRange = null;

      ctx.handleRangeChange();
      expect(ctx.selectedStage).toBeNull();
    });

    it('selects stage and expands test matching the range', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = {
        version: 1, runId: 'r', startedAt: null, finishedAt: null,
        totalSamples: 0, channels: {},
        steps: [
          { name: 'test_boot', module: 'power', startedAt: 100, finishedAt: 200 },
        ],
      };
      ctx.liveTests = [
        makeTest({ name: 'test_boot', module: 'power', expanded: false }),
        makeTest({ name: 'test_other', module: 'power', expanded: true }),
      ];
      ctx.selectedRange = { start: 100, end: 200 };

      ctx.handleRangeChange();

      expect(ctx.selectedStage).toBe('power');
      expect(ctx.findTest('test_boot', 'power')!.expanded).toBe(true);
      expect(ctx.findTest('test_other', 'power')!.expanded).toBe(false);
    });

    it('matches range approximately (within 1 second tolerance)', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = {
        version: 1, runId: 'r', startedAt: null, finishedAt: null,
        totalSamples: 0, channels: {},
        steps: [
          { name: 'test_a', module: 'mod', startedAt: 100, finishedAt: 200 },
        ],
      };
      ctx.liveTests = [makeTest({ name: 'test_a', module: 'mod', expanded: false })];
      ctx.selectedRange = { start: 100.5, end: 199.8 };

      ctx.handleRangeChange();

      expect(ctx.findTest('test_a', 'mod')!.expanded).toBe(true);
    });

    it('does not expand when range does not match any step', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.telemetryManifest = {
        version: 1, runId: 'r', startedAt: null, finishedAt: null,
        totalSamples: 0, channels: {},
        steps: [
          { name: 'test_a', module: 'mod', startedAt: 100, finishedAt: 200 },
        ],
      };
      ctx.liveTests = [makeTest({ name: 'test_a', module: 'mod', expanded: false })];
      ctx.selectedRange = { start: 500, end: 600 };

      ctx.handleRangeChange();

      expect(ctx.findTest('test_a', 'mod')!.expanded).toBe(false);
    });
  });

  // ================================================================
  // 20. checkTelemetryFetch
  // ================================================================

  describe('checkTelemetryFetch', () => {
    beforeEach(() => {
      vi.mocked(apiFetch).mockResolvedValue({ data: null });
    });

    it('does nothing when run is null', () => {
      ctx.run = null;
      ctx.checkTelemetryFetch();
      // apiFetch should not be called for telemetry manifest
      expect(apiFetch).not.toHaveBeenCalledWith(expect.stringContaining('telemetry'));
    });

    it('does nothing when run is ACTIVE', () => {
      ctx.run = makeRun({ status: 'ACTIVE' }) as any;
      ctx.checkTelemetryFetch();
      expect(apiFetch).not.toHaveBeenCalledWith(expect.stringContaining('telemetry'));
    });

    it('does nothing when run is PENDING', () => {
      ctx.run = makeRun({ status: 'PENDING' }) as any;
      ctx.checkTelemetryFetch();
      expect(apiFetch).not.toHaveBeenCalledWith(expect.stringContaining('telemetry'));
    });

    it('fetches manifest when run is completed', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.checkTelemetryFetch();
      expect(apiFetch).toHaveBeenCalledWith('/v2/sessions/run-123/telemetry/manifest');
    });

    it('only fetches manifest once (idempotent)', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.checkTelemetryFetch();
      ctx.checkTelemetryFetch();
      ctx.checkTelemetryFetch();

      const telemetryCalls = vi.mocked(apiFetch).mock.calls.filter(
        c => (c[0] as string).includes('telemetry')
      );
      expect(telemetryCalls).toHaveLength(1);
    });
  });

  // ================================================================
  // 21. tryInitialFocus
  // ================================================================

  describe('tryInitialFocus', () => {
    it('does nothing when run is null', () => {
      ctx.run = null;
      ctx.liveTests = [makeTest({ status: 'running' })];

      ctx.tryInitialFocus();

      expect(ctx.autoFollow).toBe(true); // default, unchanged
      expect(ctx.liveRunning).toBe(false);
    });

    it('does nothing when run is not ACTIVE', () => {
      ctx.run = makeRun({ status: 'COMPLETED' }) as any;
      ctx.liveTests = [makeTest({ status: 'running' })];

      ctx.tryInitialFocus();

      expect(ctx.liveRunning).toBe(false);
    });

    it('does nothing when no running test exists', () => {
      ctx.run = makeRun({ status: 'ACTIVE' }) as any;
      ctx.liveTests = [makeTest({ status: 'passed' })];

      ctx.tryInitialFocus();

      expect(ctx.liveRunning).toBe(false);
    });

    it('expands the running test and selects its stage', () => {
      ctx.run = makeRun({ status: 'ACTIVE' }) as any;
      ctx.liveTests = [
        makeTest({ name: 'done', module: 'mod', status: 'passed', expanded: true }),
        makeTest({ name: 'running_test', module: 'power', status: 'running', expanded: false }),
      ];

      ctx.tryInitialFocus();

      expect(ctx.liveRunning).toBe(true);
      expect(ctx.autoFollow).toBe(true);
      expect(ctx.selectedStage).toBe('power');
      expect(ctx.findTest('running_test', 'power')!.expanded).toBe(true);
      expect(ctx.findTest('done', 'mod')!.expanded).toBe(false);
    });

    it('only runs once (idempotent)', () => {
      ctx.run = makeRun({ status: 'ACTIVE' }) as any;
      ctx.liveTests = [
        makeTest({ name: 'test_run', module: 'mod', status: 'running' }),
      ];

      ctx.tryInitialFocus();
      // Collapse the test manually
      ctx.findTest('test_run', 'mod')!.expanded = false;

      ctx.tryInitialFocus();
      // Should not re-expand because initial focus already done
      expect(ctx.findTest('test_run', 'mod')!.expanded).toBe(false);
    });
  });

  // ================================================================
  // 22. cancelRun
  // ================================================================

  describe('cancelRun', () => {
    beforeEach(() => {
      vi.mocked(api.post).mockResolvedValue(undefined);
      vi.mocked(apiFetch).mockImplementation(async (url: string) => {
        if (url.includes('/artifacts')) return { data: [] };
        if (url.includes('/telemetry')) return { data: null };
        return { data: makeRun({ status: 'CANCELLED' }) };
      });
      vi.mocked(subscribeValidationRunWithLogs).mockReturnValue(vi.fn());
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ data: [] }),
        text: vi.fn().mockResolvedValue(''),
      });
    });

    it('sets cancelling to true during operation', async () => {
      let cancellingDuringOp = false;
      vi.mocked(api.post).mockImplementation(async () => {
        cancellingDuringOp = ctx.cancelling;
        return undefined;
      });

      await ctx.cancelRun();

      expect(cancellingDuringOp).toBe(true);
      expect(ctx.cancelling).toBe(false);
    });

    it('marks queued and running tests as skipped', async () => {
      ctx.liveTests = [
        makeTest({ name: 't1', module: 'm', status: 'passed' }),
        makeTest({ name: 't2', module: 'm', status: 'running' }),
        makeTest({ name: 't3', module: 'm', status: 'queued' }),
      ];

      await ctx.cancelRun();

      expect(ctx.findTest('t1', 'm')!.status).toBe('passed');
      expect(ctx.findTest('t2', 'm')!.status).toBe('skipped');
      expect(ctx.findTest('t3', 'm')!.status).toBe('skipped');
    });

    it('sets liveRunning=false and liveFinished=true', async () => {
      ctx.liveRunning = true;

      await ctx.cancelRun();

      expect(ctx.liveRunning).toBe(false);
      expect(ctx.liveFinished).toBe(true);
    });

    it('sets error on failure', async () => {
      vi.mocked(api.post).mockRejectedValue(new Error('Network error'));

      await ctx.cancelRun();

      expect(ctx.error).toBe('Network error');
    });
  });

  // ================================================================
  // 23. triggerRun
  // ================================================================

  describe('triggerRun', () => {
    beforeEach(() => {
      vi.mocked(api.post).mockResolvedValue(undefined);
      vi.mocked(apiFetch).mockImplementation(async (url: string) => {
        if (url.includes('/artifacts')) return { data: [] };
        return { data: makeRun() };
      });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ data: [] }),
        text: vi.fn().mockResolvedValue(''),
      });
    });

    it('posts trigger request with trimmed firmware version', async () => {
      ctx.triggerFwVersion = '  v1.0.0  ';

      await ctx.triggerRun();

      expect(api.post).toHaveBeenCalledWith('/v2/sessions/run-123/trigger', {
        firmwareVersion: 'v1.0.0',
      });
    });

    it('resets trigger UI state on success', async () => {
      ctx.showTrigger = true;
      ctx.triggerFwVersion = 'v1.0.0';

      await ctx.triggerRun();

      expect(ctx.showTrigger).toBe(false);
      expect(ctx.triggerFwVersion).toBe('');
    });

    it('sets triggering during the operation', async () => {
      let triggeringDuringOp = false;
      vi.mocked(api.post).mockImplementation(async () => {
        triggeringDuringOp = ctx.triggering;
        return undefined;
      });

      await ctx.triggerRun();

      expect(triggeringDuringOp).toBe(true);
      expect(ctx.triggering).toBe(false);
    });

    it('sets error on failure', async () => {
      vi.mocked(api.post).mockRejectedValue(new Error('Trigger failed'));

      await ctx.triggerRun();

      expect(ctx.error).toBe('Trigger failed');
    });
  });

  // ================================================================
  // 24. startDemo
  // ================================================================

  describe('startDemo', () => {
    beforeEach(() => {
      vi.mocked(api.post).mockResolvedValue(undefined);
    });

    it('resets live state before starting', async () => {
      ctx.liveTests = [makeTest()];
      ctx.liveRunning = true;
      ctx.liveFinished = true;
      ctx.liveSummary = { total: 1, passed: 1, failed: 0, errors: 0, durationS: 1 };
      ctx.selectedStage = 'mod';

      await ctx.startDemo('happy_path');

      expect(ctx.liveTests).toEqual([]);
      expect(ctx.liveRunning).toBe(false);
      expect(ctx.liveFinished).toBe(false);
      expect(ctx.liveSummary).toBeNull();
      expect(ctx.selectedStage).toBeNull();
    });

    it('sets simulating to true', async () => {
      let simulatingDuringOp = false;
      vi.mocked(api.post).mockImplementation(async () => {
        simulatingDuringOp = ctx.simulating;
        return undefined;
      });

      await ctx.startDemo('happy_path');

      expect(simulatingDuringOp).toBe(true);
    });

    it('posts correct demo URL with scenario and speed', async () => {
      await ctx.startDemo('failure_case');

      expect(api.post).toHaveBeenCalledWith(
        '/v2/sessions/run-123/demo/simulate?speed=0.1&scenario=failure_case'
      );
    });

    it('sets error and clears simulating on failure', async () => {
      vi.mocked(api.post).mockRejectedValue(new Error('Demo error'));

      await ctx.startDemo('bad_scenario');

      expect(ctx.error).toBe('Demo error');
      expect(ctx.simulating).toBe(false);
    });
  });
});
