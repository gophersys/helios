<script lang="ts">
  import { Activity, WifiOff, Radio, Settings, ArrowUpCircle, HardDrive, Cpu } from 'lucide-svelte';
  import type { IcleDevice, IcleDeviceStatus } from '$lib/types/icle';

  let { device, onclick }: { device: IcleDevice; onclick?: () => void } = $props();

  const statusConfig: Record<IcleDeviceStatus, { color: string; bg: string; icon: typeof Activity; label: string }> = {
    ONLINE: { color: 'text-success', bg: 'bg-success-muted', icon: Activity, label: 'Online' },
    OFFLINE: { color: 'text-error', bg: 'bg-error-muted', icon: WifiOff, label: 'Offline' },
    LOGGING: { color: 'text-accent', bg: 'bg-accent-muted', icon: Radio, label: 'Logging' },
    CONFIG: { color: 'text-warning', bg: 'bg-warning-muted', icon: Settings, label: 'Configuring' },
    BOOT: { color: 'text-info', bg: 'bg-info-muted', icon: Cpu, label: 'Booting' },
    OTA: { color: 'text-warning', bg: 'bg-warning-muted', icon: ArrowUpCircle, label: 'Updating' },
  };

  const config = $derived(statusConfig[device.status] || statusConfig.OFFLINE);
  const StatusIcon = $derived(config.icon);

  function formatUptime(seconds: number | undefined): string {
    if (!seconds) return '--';
    const s = Math.floor(seconds);
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  }

  function formatBytes(bytes: number | undefined): string {
    if (!bytes) return '--';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function formatRssi(rssi: number | undefined): string {
    if (rssi === undefined) return '--';
    return `${rssi} dBm`;
  }
</script>

<button
  class="w-full text-left rounded-lg border border-border bg-surface-1 p-4 transition-colors hover:bg-surface-2 focus:outline-none focus:ring-2 focus:ring-accent"
  onclick={onclick}
>
  <!-- Header: Device ID + Status -->
  <div class="flex items-start justify-between gap-3 mb-3">
    <div class="min-w-0 flex-1">
      <h3 class="text-sm font-semibold text-text-primary truncate font-mono">
        {device.name || device.deviceId}
      </h3>
      {#if device.name}
        <p class="text-2xs text-text-tertiary font-mono truncate">{device.deviceId}</p>
      {/if}
    </div>
    <div class="flex items-center gap-1.5 rounded-full px-2 py-1 {config.bg}">
      <StatusIcon size={12} class={config.color} />
      <span class="text-2xs font-medium {config.color}">{config.label}</span>
    </div>
  </div>

  <!-- Connection Info -->
  <div class="grid grid-cols-2 gap-2 text-2xs mb-3">
    <div>
      <span class="text-text-tertiary">IP Address</span>
      <p class="font-medium text-text-primary font-mono">{device.ipAddress || '--'}</p>
    </div>
    <div>
      <span class="text-text-tertiary">MAC Address</span>
      <p class="font-medium text-text-primary font-mono text-[10px]">{device.macAddress || '--'}</p>
    </div>
  </div>

  <!-- Firmware + Status Data -->
  <div class="border-t border-border pt-3 space-y-2">
    <div class="flex items-center justify-between text-2xs">
      <span class="text-text-tertiary">Firmware</span>
      <span class="font-medium text-text-secondary">{device.firmwareVersion || '--'}</span>
    </div>

    {#if device.lastStatusData}
      <div class="flex items-center justify-between text-2xs">
        <span class="text-text-tertiary">Uptime</span>
        <span class="font-medium text-text-secondary tabular-nums">
          {formatUptime(device.lastStatusData.uptime_seconds)}
        </span>
      </div>
      <div class="flex items-center justify-between text-2xs">
        <span class="text-text-tertiary">Free Heap</span>
        <span class="font-medium text-text-secondary tabular-nums">
          {formatBytes(device.lastStatusData.free_heap_bytes)}
        </span>
      </div>
      <div class="flex items-center justify-between text-2xs">
        <span class="text-text-tertiary">WiFi RSSI</span>
        <span class="font-medium text-text-secondary tabular-nums">
          {formatRssi(device.lastStatusData.wifi_rssi)}
        </span>
      </div>
      {#if device.lastStatusData.sd_card_free_mb !== undefined}
        <div class="flex items-center justify-between text-2xs">
          <span class="text-text-tertiary flex items-center gap-1">
            <HardDrive size={10} /> SD Card
          </span>
          <span class="font-medium text-text-secondary tabular-nums">
            {device.lastStatusData.sd_card_free_mb.toFixed(1)} MB free
          </span>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Registration Badge -->
  {#if !device.registered}
    <div class="mt-3 flex items-center gap-1.5 rounded bg-accent-muted px-2 py-1">
      <span class="h-1.5 w-1.5 rounded-full bg-accent animate-pulse"></span>
      <span class="text-2xs font-medium text-accent">Discovered - Click to register</span>
    </div>
  {/if}

  <!-- Last Heartbeat -->
  {#if device.lastHeartbeat}
    <p class="mt-2 text-[10px] text-text-tertiary">
      Last seen: {new Date(device.lastHeartbeat).toLocaleString()}
    </p>
  {/if}
</button>
