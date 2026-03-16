import { subscribeIcle } from '$lib/services/websocket';
import type {
  IcleDevice,
  IcleDeviceStatus,
  IcleStatusData,
  IclePowerReading,
  IcleUpdateEvent
} from '$lib/types/icle';

/**
 * Ring buffer size for power readings (600 samples = 60s at 10Hz).
 */
const MAX_POWER_SAMPLES = 600;

/**
 * Svelte 5 rune-based store for ICLE device observability data.
 * Manages real-time subscriptions to device status and power readings.
 */
class IcleStore {
  private currentDeviceId = $state<string | null>(null);
  private unsubscribeFn: (() => void) | null = null;

  // Reactive state
  device = $state<IcleDevice | null>(null);
  status = $state<IcleDeviceStatus>('OFFLINE');
  statusData = $state<IcleStatusData | null>(null);
  powerHistory = $state<IclePowerReading[]>([]);
  error = $state<string | null>(null);
  isConnected = $state<boolean>(false);
  lastUpdate = $state<number | null>(null);

  /**
   * Subscribe to real-time updates for a specific ICLE device.
   * Automatically unsubscribes from any previous subscription.
   *
   * @param deviceId - ICLE device identifier
   */
  subscribe(deviceId: string): void {
    // Cleanup any existing subscription
    if (this.unsubscribeFn) {
      this.unsubscribeFn();
    }

    // Reset state
    this.currentDeviceId = deviceId;
    this.device = null;
    this.status = 'OFFLINE';
    this.statusData = null;
    this.powerHistory = [];
    this.error = null;
    this.lastUpdate = null;

    // Start new subscription
    this.unsubscribeFn = subscribeIcle(
      deviceId,
      (data: IcleUpdateEvent) => {
        // Update reactive state based on received data
        this.status = data.status;
        this.statusData = data.statusData;
        this.lastUpdate = data.timestamp;
        this.isConnected = true;
        this.error = null;

        // Append power readings to history (ring buffer)
        if (data.statusData?.power_readings) {
          const newReadings = [...this.powerHistory, ...data.statusData.power_readings];
          this.powerHistory = newReadings.length > MAX_POWER_SAMPLES
            ? newReadings.slice(newReadings.length - MAX_POWER_SAMPLES)
            : newReadings;
        }
      },
      (err: string) => {
        this.error = err;
        this.isConnected = false;
      }
    );
  }

  /**
   * Set the initial device data (from API fetch).
   */
  setDevice(device: IcleDevice): void {
    this.device = device;
    this.status = device.status;
    this.statusData = device.lastStatusData;
  }

  /**
   * Clear power history buffer.
   */
  clearPowerHistory(): void {
    this.powerHistory = [];
  }

  /**
   * Unsubscribe from current device stream and clear state.
   */
  unsubscribe(): void {
    if (this.unsubscribeFn) {
      this.unsubscribeFn();
      this.unsubscribeFn = null;
    }

    // Clear state
    this.currentDeviceId = null;
    this.device = null;
    this.status = 'OFFLINE';
    this.statusData = null;
    this.powerHistory = [];
    this.error = null;
    this.isConnected = false;
    this.lastUpdate = null;
  }

  /**
   * Get the currently subscribed device ID.
   */
  get deviceId(): string | null {
    return this.currentDeviceId;
  }
}

/**
 * Singleton instance for ICLE store.
 * Use this to manage real-time ICLE device subscriptions.
 */
export const icleStore = new IcleStore();
