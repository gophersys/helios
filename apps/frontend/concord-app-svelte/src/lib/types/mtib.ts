/**
 * MTIB (Manufacturing Test Interface Board) TypeScript types.
 * Used for real-time observability and logic analyzer subscriptions.
 */

/**
 * Power channel reading from MTIB.
 */
export interface PowerReading {
  channel: number;
  enabled: boolean;
  voltage_v: number;
  current_ma: number;
}

/**
 * GPIO pin state from MTIB.
 */
export interface GpioState {
  pin: number;
  direction: 'INPUT' | 'OUTPUT';
  value: boolean;
}

/**
 * ADC channel reading from MTIB.
 */
export interface AdcReading {
  channel: number;
  voltage_v: number;
}

/**
 * System resource metrics from MTIB.
 */
export interface SystemMetrics {
  cpu_usage_percent: number;
  memory_usage_mb: number;
  uptime_seconds: number;
}

/**
 * Snapshot of MTIB observability data.
 * Features are optional depending on subscription.
 */
export interface ObservabilitySnapshot {
  nodeId: string;
  timestamp: number;
  power?: { channels: PowerReading[] };
  gpio?: { pins: GpioState[] };
  adc?: { channels: AdcReading[] };
  system?: SystemMetrics;
}

/**
 * Single sample from the logic analyzer.
 * timestamp_ns is nanoseconds since capture start.
 * channel_states is a bitmask of digital channel states.
 */
export interface AnalyzerSample {
  timestamp_ns: number;
  channel_states: number;
}
