import { subscribeAnalyzer } from '$lib/services/websocket';
import type { AnalyzerSample } from '$lib/types/mtib';

/**
 * Svelte 5 rune-based store for MTIB logic analyzer captures.
 * Manages streaming sample data from analyzer captures.
 */
class AnalyzerStore {
  private currentNodeId = $state<string | null>(null);
  private currentCaptureId = $state<string | null>(null);
  private unsubscribeFn: (() => void) | null = null;

  // Reactive state
  samples = $state<AnalyzerSample[]>([]);
  isCapturing = $state<boolean>(false);
  captureComplete = $state<boolean>(false);
  totalSamples = $state<number>(0);
  error = $state<string | null>(null);

  /**
   * Start capturing analyzer data for a specific MTIB node.
   * Automatically stops any previous capture.
   *
   * @param nodeId - MTIB node identifier
   * @param captureId - Unique capture session identifier
   */
  startCapture(nodeId: string, captureId: string): void {
    // Cleanup any existing capture
    if (this.unsubscribeFn) {
      this.unsubscribeFn();
    }

    // Reset state
    this.currentNodeId = nodeId;
    this.currentCaptureId = captureId;
    this.samples = [];
    this.isCapturing = true;
    this.captureComplete = false;
    this.totalSamples = 0;
    this.error = null;

    // Start new subscription
    this.unsubscribeFn = subscribeAnalyzer(
      nodeId,
      captureId,
      (data: { samples: AnalyzerSample[] }) => {
        // Accumulate samples as chunks arrive
        this.samples = [...this.samples, ...data.samples];
        this.totalSamples = this.samples.length;
      },
      (data: { status: string; totalSamples: number }) => {
        // Capture complete
        this.isCapturing = false;
        this.captureComplete = true;
        this.totalSamples = data.totalSamples;
        this.error = null;
      },
      (err: string) => {
        // Capture error
        this.error = err;
        this.isCapturing = false;
        this.captureComplete = false;
      }
    );
  }

  /**
   * Stop the current analyzer capture and clean up.
   */
  stopCapture(): void {
    if (this.unsubscribeFn) {
      this.unsubscribeFn();
      this.unsubscribeFn = null;
    }

    this.isCapturing = false;
  }

  /**
   * Clear all capture data and reset state.
   */
  clear(): void {
    this.stopCapture();

    this.currentNodeId = null;
    this.currentCaptureId = null;
    this.samples = [];
    this.captureComplete = false;
    this.totalSamples = 0;
    this.error = null;
  }

  /**
   * Get the currently active node ID.
   */
  get nodeId(): string | null {
    return this.currentNodeId;
  }

  /**
   * Get the currently active capture ID.
   */
  get captureId(): string | null {
    return this.currentCaptureId;
  }
}

/**
 * Singleton instance for MTIB analyzer store.
 * Use this to manage logic analyzer capture subscriptions.
 */
export const analyzerStore = new AnalyzerStore();
