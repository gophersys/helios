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
  samplesCollected = $state<number>(0);
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
    this.samplesCollected = 0;
    this.error = null;
  }

  /**
   * Connect to analyzer websocket for a node.
   * @param nodeId - MTIB node identifier
   */
  connect(nodeId: string): void {
    this.currentNodeId = nodeId;
    // WebSocket connection would be established here
  }

  /**
   * Disconnect from analyzer websocket.
   */
  disconnect(): void {
    this.stopCapture();
    this.currentNodeId = null;
  }

  /**
   * Start a new capture with configuration.
   * @param config - Capture configuration
   */
  async start(_config: { sampleRate: number; duration: number; channels: number[] }): Promise<void> {
    if (!this.currentNodeId) {
      throw new Error('Not connected to a node');
    }
    // In a full implementation, this would trigger a capture via API/WebSocket
    this.isCapturing = true;
    this.samples = [];
    this.samplesCollected = 0;
    this.error = null;
  }

  /**
   * Stop the current capture.
   */
  stop(): void {
    this.stopCapture();
  }

  /**
   * Export samples as CSV and trigger download.
   * @param filename - Optional filename for download
   */
  exportCsv(filename?: string): void {
    const header = 'timestamp_ns,channel_states';
    const rows = this.samples.map(s => `${s.timestamp_ns},${s.channel_states}`);
    const csv = [header, ...rows].join('\n');
    this.downloadFile(csv, filename || 'analyzer-export.csv', 'text/csv');
  }

  /**
   * Export samples as VCD (Value Change Dump) and trigger download.
   * @param filename - Optional filename for download
   */
  exportVcd(filename?: string): void {
    // Basic VCD format
    const lines: string[] = [
      '$timescale 1ns $end',
      '$scope module capture $end',
    ];
    // Add variable declarations for 8 channels
    for (let ch = 0; ch < 8; ch++) {
      lines.push(`$var wire 1 ${String.fromCharCode(33 + ch)} ch${ch} $end`);
    }
    lines.push('$upscope $end', '$enddefinitions $end');
    // Add data - expand channel_states bitmask to individual channel values
    for (const sample of this.samples) {
      lines.push(`#${sample.timestamp_ns}`);
      for (let ch = 0; ch < 8; ch++) {
        const value = (sample.channel_states >> ch) & 1;
        lines.push(`${value}${String.fromCharCode(33 + ch)}`);
      }
    }
    const vcd = lines.join('\n');
    this.downloadFile(vcd, filename || 'analyzer-export.vcd', 'text/plain');
  }

  /**
   * Helper to trigger file download in browser.
   */
  private downloadFile(content: string, filename: string, mimeType: string): void {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
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
