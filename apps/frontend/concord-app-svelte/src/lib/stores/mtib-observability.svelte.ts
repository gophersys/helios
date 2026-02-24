import { subscribeMtibObservability } from '$lib/services/websocket';
import type {
  PowerReading,
  GpioState,
  AdcReading,
  SystemMetrics,
  ObservabilitySnapshot
} from '$lib/types/mtib';

/**
 * Svelte 5 rune-based store for MTIB observability data.
 * Manages real-time subscriptions to power, GPIO, ADC, and system metrics.
 */
class MtibObservabilityStore {
  private currentNodeId = $state<string | null>(null);
  private unsubscribeFn: (() => void) | null = null;

  // Reactive state
  powerReadings = $state<PowerReading[] | null>(null);
  gpioStates = $state<GpioState[] | null>(null);
  adcReadings = $state<AdcReading[] | null>(null);
  systemMetrics = $state<SystemMetrics | null>(null);
  error = $state<string | null>(null);
  isConnected = $state<boolean>(false);
  lastUpdate = $state<number | null>(null);

  /**
   * Subscribe to observability updates for a specific MTIB node.
   * Automatically unsubscribes from any previous subscription.
   *
   * @param nodeId - MTIB node identifier
   * @param features - Array of features to observe: 'power', 'gpio', 'adc', 'system'
   */
  subscribe(nodeId: string, features: string[]): void {
    // Cleanup any existing subscription
    if (this.unsubscribeFn) {
      this.unsubscribeFn();
    }

    // Reset state
    this.currentNodeId = nodeId;
    this.powerReadings = null;
    this.gpioStates = null;
    this.adcReadings = null;
    this.systemMetrics = null;
    this.error = null;
    this.lastUpdate = null;

    // Start new subscription
    this.unsubscribeFn = subscribeMtibObservability(
      nodeId,
      features,
      (data: ObservabilitySnapshot) => {
        // Update reactive state based on received data
        if (data.power) {
          this.powerReadings = data.power.channels;
        }
        if (data.gpio) {
          this.gpioStates = data.gpio.pins;
        }
        if (data.adc) {
          this.adcReadings = data.adc.channels;
        }
        if (data.system) {
          this.systemMetrics = data.system;
        }

        this.lastUpdate = data.timestamp;
        this.isConnected = true;
        this.error = null;
      },
      (err: string) => {
        this.error = err;
        this.isConnected = false;
      }
    );
  }

  /**
   * Unsubscribe from current observability stream and clear state.
   */
  unsubscribe(): void {
    if (this.unsubscribeFn) {
      this.unsubscribeFn();
      this.unsubscribeFn = null;
    }

    // Clear state
    this.currentNodeId = null;
    this.powerReadings = null;
    this.gpioStates = null;
    this.adcReadings = null;
    this.systemMetrics = null;
    this.error = null;
    this.isConnected = false;
    this.lastUpdate = null;
  }

  /**
   * Get the currently subscribed node ID.
   */
  get nodeId(): string | null {
    return this.currentNodeId;
  }
}

/**
 * Singleton instance for MTIB observability store.
 * Use this to manage real-time power, GPIO, ADC, and system metrics subscriptions.
 */
export const mtibObservabilityStore = new MtibObservabilityStore();
