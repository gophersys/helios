/**
 * ICLE (Industrial Current Logger for Embedded) TypeScript types.
 * Used for device management, real-time power monitoring, and log downloads.
 */

/**
 * ICLE device status values.
 */
export type IcleDeviceStatus = 'ONLINE' | 'OFFLINE' | 'LOGGING' | 'CONFIG' | 'BOOT' | 'OTA';

/**
 * ICLE device model.
 */
export interface IcleDevice {
  id: string;
  deviceId: string;
  name: string | null;
  ipAddress: string | null;
  macAddress: string | null;
  firmwareVersion: string | null;
  status: IcleDeviceStatus;
  registered: boolean;
  lastHeartbeat: string | null;
  lastStatusData: IcleStatusData | null;
  createdAt: string;
  updatedAt: string;
}

/**
 * Status data reported by an ICLE device.
 */
export interface IcleStatusData {
  uptime_seconds: number;
  free_heap_bytes: number;
  wifi_rssi: number;
  sd_card_free_mb: number;
  current_log_file: string | null;
  power_readings: IclePowerReading[];
}

/**
 * Single power reading from an ICLE device.
 */
export interface IclePowerReading {
  timestamp: number;
  voltage_mv: number;
  current_ma: number;
  power_mw: number;
}

/**
 * Pending command queued for an ICLE device.
 */
export interface IclePendingCommand {
  id: string;
  commandType: string;
  payload: Record<string, unknown>;
  priority: number;
  createdAt: string;
  expiresAt: string | null;
  acknowledged: boolean;
}

/**
 * Log file metadata from an ICLE device.
 */
export interface IcleLogFile {
  filename: string;
  size_bytes: number;
  created_at: string;
  is_active: boolean;
}

/**
 * Configuration for an ICLE device.
 */
export interface IcleConfig {
  sample_rate_hz: number;
  log_interval_ms: number;
  wifi_ssid: string | null;
  ntp_server: string | null;
  mqtt_broker: string | null;
  mqtt_topic: string | null;
}

/**
 * WebSocket update event for ICLE device.
 */
export interface IcleUpdateEvent {
  deviceId: string;
  status: IcleDeviceStatus;
  statusData: IcleStatusData | null;
  timestamp: number;
}

/**
 * Discovered ICLE device (not yet registered).
 */
export interface DiscoveredIcleDevice {
  deviceId: string;
  ipAddress: string;
  macAddress: string | null;
  firmwareVersion: string | null;
  discoveredAt: string;
}

/**
 * Result of device discovery scan.
 */
export interface IcleDiscoveryResult {
  registered: IcleDevice[];
  discovered: DiscoveredIcleDevice[];
}
