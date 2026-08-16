/**
 * WebSocket helpers for the E2E story suite.
 * Subscribe to validation run events via the /kubernetes namespace WebSocket.
 */
import type { Page } from '@playwright/test';

export interface TestStartEvent {
  testName: string;
  runId: string;
  timestamp: string;
}

export interface TestResultEvent {
  testName: string;
  runId: string;
  status: string;
  duration?: number;
  skipped?: boolean;
  timestamp: string;
}

export interface RunFinishEvent {
  runId: string;
  status: string;
  timestamp: string;
}

export interface RunEventCollector {
  testStarts: TestStartEvent[];
  testResults: TestResultEvent[];
  runFinished: RunFinishEvent | null;
  waitForTestResult(testName: string, timeout?: number): Promise<TestResultEvent>;
  waitForRunFinish(timeout?: number): Promise<RunFinishEvent>;
  dispose(): void;
}

/**
 * Subscribe to validation run events by evaluating a WebSocket client in the page context.
 * Events are collected and can be awaited.
 */
export async function subscribeToRun(page: Page, runId: string): Promise<RunEventCollector> {
  const testStarts: TestStartEvent[] = [];
  const testResults: TestResultEvent[] = [];
  let runFinished: RunFinishEvent | null = null;
  let disposed = false;

  // Inject a WebSocket listener into the page
  await page.evaluate(
    ({ runId: rid }) => {
      const baseUrl = window.location.origin.replace(/^http/, 'ws');
      const ws = new WebSocket(`${baseUrl}/ws/kubernetes`);
      (window as any).__e2eWs = ws;
      (window as any).__e2eWsEvents = [];

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.runId === rid || !data.runId) {
            (window as any).__e2eWsEvents.push(data);
          }
        } catch {
          // ignore non-JSON messages
        }
      };
    },
    { runId },
  );

  // Poll for events from the page context
  async function pollEvents(): Promise<void> {
    if (disposed) return;
    try {
      const events = await page.evaluate(() => {
        const evts = (window as any).__e2eWsEvents || [];
        (window as any).__e2eWsEvents = [];
        return evts;
      });

      for (const evt of events) {
        if (evt.type === 'validation_test_start') {
          testStarts.push(evt as TestStartEvent);
        } else if (evt.type === 'validation_test_result') {
          testResults.push(evt as TestResultEvent);
        } else if (evt.type === 'validation_run_finish') {
          runFinished = evt as RunFinishEvent;
        }
      }
    } catch {
      // Page may have navigated away
    }
  }

  const pollInterval = setInterval(pollEvents, 500);

  return {
    testStarts,
    testResults,
    get runFinished() {
      return runFinished;
    },

    async waitForTestResult(testName: string, timeout = 60_000): Promise<TestResultEvent> {
      const start = Date.now();
      while (Date.now() - start < timeout) {
        await pollEvents();
        const result = testResults.find((r) => r.testName === testName);
        if (result) return result;
        await new Promise((r) => setTimeout(r, 500));
      }
      throw new Error(`Timed out waiting for test result: ${testName}`);
    },

    async waitForRunFinish(timeout = 300_000): Promise<RunFinishEvent> {
      const start = Date.now();
      while (Date.now() - start < timeout) {
        await pollEvents();
        if (runFinished) return runFinished;
        await new Promise((r) => setTimeout(r, 1_000));
      }
      throw new Error(`Timed out waiting for run finish (runId: ${runId})`);
    },

    dispose(): void {
      disposed = true;
      clearInterval(pollInterval);
      page
        .evaluate(() => {
          const ws = (window as any).__e2eWs;
          if (ws) ws.close();
          delete (window as any).__e2eWs;
          delete (window as any).__e2eWsEvents;
        })
        .catch(() => {});
    },
  };
}
