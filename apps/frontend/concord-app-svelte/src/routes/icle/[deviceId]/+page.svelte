<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate } from '$app/navigation';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    ArrowLeft, Activity, WifiOff, Radio, Settings, ArrowUpCircle, Cpu,
    Loader2, RefreshCw, Pencil, Trash2, Check, X, Play, Square,
    Upload, Send
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { icleStore } from '$lib/stores/icle.svelte';
  import { LoadingState, ErrorAlert, ConfirmDeleteDialog, Modal } from '$lib/components/ui';
  import { PowerChart, LogList } from '$lib/components/icle';
  import type { IcleDevice, IcleDeviceStatus, IcleLogFile, IcleConfig, IclePendingCommand } from '$lib/types/icle';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('devices:manage'));

  const deviceId = $derived($page.params.deviceId as string);

  let device = $state<IcleDevice | null>(null);
  let logs = $state<IcleLogFile[]>([]);
  let config = $state<IcleConfig | null>(null);
  let pendingCommands = $state<IclePendingCommand[]>([]);
  let loading = $state(true);
  let logsLoading = $state(false);
  let error = $state<string | null>(null);
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  // Edit form state
  let editing = $state(false);
  let editName = $state('');
  let submitting = $state(false);

  // Config modal state
  let showConfigModal = $state(false);
  let configForm = $state<Partial<IcleConfig>>({});

  // OTA modal state
  let showOtaModal = $state(false);
  let otaUrl = $state('');

  // Delete confirmation
  let showDeleteConfirm = $state(false);

  const isOnline = $derived(device?.status !== 'OFFLINE');
  const isLogging = $derived(device?.status === 'LOGGING');

  const statusConfig: Record<IcleDeviceStatus, { color: string; bg: string; icon: typeof Activity; label: string }> = {
    ONLINE: { color: 'text-success', bg: 'bg-success-muted', icon: Activity, label: 'Online' },
    OFFLINE: { color: 'text-error', bg: 'bg-error-muted', icon: WifiOff, label: 'Offline' },
    LOGGING: { color: 'text-accent', bg: 'bg-accent-muted', icon: Radio, label: 'Logging' },
    CONFIG: { color: 'text-warning', bg: 'bg-warning-muted', icon: Settings, label: 'Configuring' },
    BOOT: { color: 'text-info', bg: 'bg-info-muted', icon: Cpu, label: 'Booting' },
    OTA: { color: 'text-warning', bg: 'bg-warning-muted', icon: ArrowUpCircle, label: 'Updating' },
  };

  async function fetchDevice() {
    try {
      const res = await apiFetch<ApiResponse<IcleDevice>>(`/v2/devices/icle/${deviceId}`);
      device = res.data;
      icleStore.setDevice(device);
      error = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to fetch device';
    } finally {
      loading = false;
    }
  }

  async function fetchLogs() {
    logsLoading = true;
    try {
      const res = await apiFetch<ApiResponse<{ logs: IcleLogFile[] }>>(`/v2/devices/icle/${deviceId}/logs`);
      logs = res.data?.logs || [];
    } catch {
      // Non-critical
    } finally {
      logsLoading = false;
    }
  }

  async function fetchConfig() {
    try {
      const res = await apiFetch<ApiResponse<IcleConfig>>(`/v2/devices/icle/${deviceId}/config`);
      config = res.data;
    } catch {
      // Non-critical
    }
  }

  async function fetchPendingCommands() {
    try {
      const res = await apiFetch<ApiResponse<{ commands: IclePendingCommand[] }>>(`/v2/devices/icle/${deviceId}/commands`);
      pendingCommands = res.data?.commands || [];
    } catch {
      // Non-critical
    }
  }

  function cleanup() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    icleStore.unsubscribe();
  }

  onMount(() => {
    if (!auth.hasPermission('devices:view')) {
      goto('/');
      return;
    }
    fetchDevice();
    fetchLogs();
    fetchConfig();
    fetchPendingCommands();

    // Subscribe to real-time updates
    icleStore.subscribe(deviceId);

    // Poll for device status
    pollInterval = setInterval(() => {
      fetchDevice();
      fetchPendingCommands();
    }, 5000);
  });

  onDestroy(() => {
    cleanup();
  });

  beforeNavigate(() => {
    cleanup();
  });

  // Edit handlers
  function startEdit() {
    editName = device?.name || '';
    editing = true;
  }

  function cancelEdit() {
    editing = false;
    editName = '';
  }

  async function saveEdit() {
    if (!device) return;
    submitting = true;
    try {
      await api.put(`/v2/devices/icle/${deviceId}`, { name: editName || null });
      await fetchDevice();
      cancelEdit();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to update device';
    } finally {
      submitting = false;
    }
  }

  // Delete handler
  async function handleDelete() {
    try {
      await api.delete(`/v2/devices/icle/${deviceId}`);
      goto('/icle');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete device';
    }
  }

  // Logging controls
  async function startLogging() {
    submitting = true;
    try {
      await api.post(`/v2/devices/icle/${deviceId}/commands`, {
        commandType: 'START_LOGGING',
        payload: {},
      });
      await fetchDevice();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to start logging';
    } finally {
      submitting = false;
    }
  }

  async function stopLogging() {
    submitting = true;
    try {
      await api.post(`/v2/devices/icle/${deviceId}/commands`, {
        commandType: 'STOP_LOGGING',
        payload: {},
      });
      await fetchDevice();
      await fetchLogs();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to stop logging';
    } finally {
      submitting = false;
    }
  }

  // Config handlers
  function openConfigModal() {
    if (config) {
      configForm = { ...config };
    }
    showConfigModal = true;
  }

  async function saveConfig() {
    submitting = true;
    try {
      await api.post(`/v2/devices/icle/${deviceId}/commands`, {
        commandType: 'SET_CONFIG',
        payload: configForm,
      });
      showConfigModal = false;
      await fetchConfig();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to push config';
    } finally {
      submitting = false;
    }
  }

  // OTA handlers
  function openOtaModal() {
    otaUrl = '';
    showOtaModal = true;
  }

  async function triggerOta() {
    if (!otaUrl) return;
    submitting = true;
    try {
      await api.post(`/v2/devices/icle/${deviceId}/commands`, {
        commandType: 'OTA_UPDATE',
        payload: { url: otaUrl },
      });
      showOtaModal = false;
      await fetchDevice();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to trigger OTA';
    } finally {
      submitting = false;
    }
  }

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
</script>

<svelte:head>
  <title>{device?.name || device?.deviceId || 'ICLE Device'} - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <!-- Header -->
  <div class="mb-6">
    <div class="flex items-center gap-2 mb-3">
      <button
        onclick={() => goto('/icle')}
        class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} />
        ICLE Devices
      </button>
    </div>

    {#if device}
      {@const statusConf = statusConfig[device.status] || statusConfig.OFFLINE}
      {@const StatusIcon = statusConf.icon}

      <div class="flex items-center justify-between gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <span class="relative flex h-3 w-3 shrink-0">
            <span class="h-3 w-3 rounded-full {isOnline ? 'bg-success' : 'bg-text-tertiary'}"></span>
            {#if isOnline}
              <span class="absolute inset-0 rounded-full bg-success animate-ping opacity-40"></span>
            {/if}
          </span>
          <div class="min-w-0">
            {#if editing}
              <div class="flex items-center gap-2">
                <input
                  type="text"
                  bind:value={editName}
                  placeholder="Device name"
                  class="rounded-lg border border-border bg-surface-0 px-2 py-1 text-sm text-text-primary focus:border-accent focus:outline-none"
                />
                <button onclick={saveEdit} disabled={submitting} class="rounded p-1 text-success hover:bg-surface-2">
                  <Check size={16} />
                </button>
                <button onclick={cancelEdit} class="rounded p-1 text-text-tertiary hover:bg-surface-2">
                  <X size={16} />
                </button>
              </div>
            {:else}
              <div class="flex items-center gap-2">
                <h1 class="text-lg font-semibold text-text-primary truncate leading-tight">
                  {device.name || device.deviceId}
                </h1>
                {#if canManage}
                  <button onclick={startEdit} class="rounded p-1 text-text-tertiary hover:text-text-primary hover:bg-surface-2">
                    <Pencil size={14} />
                  </button>
                {/if}
              </div>
            {/if}
            <div class="flex items-center gap-2 mt-0.5">
              <span class="text-2xs font-mono text-text-tertiary">{device.deviceId}</span>
              {#if device.firmwareVersion}
                <span class="rounded bg-surface-2 px-1.5 py-0.5 text-[9px] font-medium text-text-secondary">
                  v{device.firmwareVersion}
                </span>
              {/if}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-3 shrink-0">
          <span class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 {statusConf.bg}">
            <StatusIcon size={10} class={statusConf.color} />
            <span class="text-2xs font-medium {statusConf.color}">{statusConf.label}</span>
          </span>

          {#if canManage}
            <div class="flex items-center gap-1">
              {#if isLogging}
                <button
                  onclick={stopLogging}
                  disabled={submitting}
                  class="flex items-center gap-1.5 rounded-lg bg-error px-3 py-1.5 text-xs font-medium text-white hover:bg-error/90 disabled:opacity-50"
                >
                  <Square size={12} />
                  Stop
                </button>
              {:else if isOnline}
                <button
                  onclick={startLogging}
                  disabled={submitting}
                  class="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                >
                  <Play size={12} />
                  Start Logging
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Loading device..." />
  {:else if error && !device}
    <ErrorAlert message={error} />
  {:else if device}
    <ErrorAlert message={error} />

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <!-- Left Column: Device Info + Controls -->
      <div class="space-y-4">
        <!-- Device Info Card -->
        <div class="card p-4">
          <h3 class="text-xs font-semibold text-text-primary uppercase tracking-wider mb-3">Device Info</h3>
          <div class="space-y-2 text-2xs">
            <div class="flex justify-between">
              <span class="text-text-tertiary">IP Address</span>
              <span class="font-mono text-text-primary">{device.ipAddress || '--'}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-text-tertiary">MAC Address</span>
              <span class="font-mono text-text-primary text-[10px]">{device.macAddress || '--'}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-text-tertiary">Firmware</span>
              <span class="font-medium text-text-primary">{device.firmwareVersion || '--'}</span>
            </div>
            {#if device.lastStatusData}
              <div class="border-t border-border pt-2 mt-2">
                <div class="flex justify-between">
                  <span class="text-text-tertiary">Uptime</span>
                  <span class="font-medium text-text-primary tabular-nums">
                    {formatUptime(device.lastStatusData.uptime_seconds)}
                  </span>
                </div>
                <div class="flex justify-between mt-1">
                  <span class="text-text-tertiary">Free Heap</span>
                  <span class="font-medium text-text-primary tabular-nums">
                    {formatBytes(device.lastStatusData.free_heap_bytes)}
                  </span>
                </div>
                <div class="flex justify-between mt-1">
                  <span class="text-text-tertiary">WiFi RSSI</span>
                  <span class="font-medium text-text-primary tabular-nums">
                    {device.lastStatusData.wifi_rssi} dBm
                  </span>
                </div>
                <div class="flex justify-between mt-1">
                  <span class="text-text-tertiary">SD Card Free</span>
                  <span class="font-medium text-text-primary tabular-nums">
                    {device.lastStatusData.sd_card_free_mb?.toFixed(1) || '--'} MB
                  </span>
                </div>
              </div>
            {/if}
            {#if device.lastHeartbeat}
              <p class="text-[10px] text-text-tertiary mt-2">
                Last seen: {new Date(device.lastHeartbeat).toLocaleString()}
              </p>
            {/if}
          </div>
        </div>

        <!-- Actions Card -->
        {#if canManage}
          <div class="card p-4">
            <h3 class="text-xs font-semibold text-text-primary uppercase tracking-wider mb-3">Actions</h3>
            <div class="space-y-2">
              <button
                onclick={openConfigModal}
                disabled={!isOnline}
                class="w-full flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs font-medium text-text-primary hover:bg-surface-3 disabled:opacity-50"
              >
                <Settings size={14} />
                Push Configuration
              </button>
              <button
                onclick={openOtaModal}
                disabled={!isOnline}
                class="w-full flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs font-medium text-text-primary hover:bg-surface-3 disabled:opacity-50"
              >
                <Upload size={14} />
                Trigger OTA Update
              </button>
              <button
                onclick={() => showDeleteConfirm = true}
                class="w-full flex items-center gap-2 rounded-lg bg-error-muted px-3 py-2 text-xs font-medium text-error hover:bg-error/20"
              >
                <Trash2 size={14} />
                Delete Device
              </button>
            </div>
          </div>
        {/if}

        <!-- Pending Commands -->
        {#if pendingCommands.length > 0}
          <div class="card p-4">
            <h3 class="text-xs font-semibold text-text-primary uppercase tracking-wider mb-3">
              Pending Commands
              <span class="ml-1 rounded-full bg-warning-muted px-1.5 py-0.5 text-[10px] font-medium text-warning">
                {pendingCommands.length}
              </span>
            </h3>
            <div class="space-y-2">
              {#each pendingCommands as cmd (cmd.id)}
                <div class="rounded-lg bg-surface-1 px-3 py-2">
                  <div class="flex items-center justify-between">
                    <span class="text-2xs font-medium text-text-primary">{cmd.commandType}</span>
                    {#if cmd.acknowledged}
                      <span class="text-[10px] text-success">ACK</span>
                    {:else}
                      <span class="text-[10px] text-warning">Pending</span>
                    {/if}
                  </div>
                  <p class="text-[10px] text-text-tertiary mt-0.5">
                    {new Date(cmd.createdAt).toLocaleString()}
                  </p>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <!-- Right Column: Power Chart + Logs -->
      <div class="lg:col-span-2 space-y-4">
        <!-- Power Chart -->
        <PowerChart readings={icleStore.powerHistory} deviceId={device.deviceId} />

        <!-- Log Files -->
        <LogList
          {logs}
          deviceId={device.id}
          loading={logsLoading}
          onRefresh={fetchLogs}
        />
      </div>
    </div>

    <!-- Delete Confirmation -->
    <ConfirmDeleteDialog
      open={showDeleteConfirm}
      entityType="ICLE Device"
      entityName={device.name || device.deviceId}
      onConfirm={handleDelete}
      onCancel={() => showDeleteConfirm = false}
    />

    <!-- Config Modal -->
    {#if showConfigModal}
      <Modal open={showConfigModal} title="Push Configuration" onclose={() => showConfigModal = false}>
        <div class="space-y-4">
          <div>
            <label for="config-sample-rate" class="block text-2xs font-medium text-text-tertiary mb-1">Sample Rate (Hz)</label>
            <input
              id="config-sample-rate"
              type="number"
              bind:value={configForm.sample_rate_hz}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label for="config-log-interval" class="block text-2xs font-medium text-text-tertiary mb-1">Log Interval (ms)</label>
            <input
              id="config-log-interval"
              type="number"
              bind:value={configForm.log_interval_ms}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label for="config-wifi-ssid" class="block text-2xs font-medium text-text-tertiary mb-1">WiFi SSID</label>
            <input
              id="config-wifi-ssid"
              type="text"
              bind:value={configForm.wifi_ssid}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label for="config-ntp-server" class="block text-2xs font-medium text-text-tertiary mb-1">NTP Server</label>
            <input
              id="config-ntp-server"
              type="text"
              bind:value={configForm.ntp_server}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <button
              onclick={() => showConfigModal = false}
              class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
            >
              Cancel
            </button>
            <button
              onclick={saveConfig}
              disabled={submitting}
              class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              <Send size={14} />
              {submitting ? 'Pushing...' : 'Push Config'}
            </button>
          </div>
        </div>
      </Modal>
    {/if}

    <!-- OTA Modal -->
    {#if showOtaModal}
      <Modal open={showOtaModal} title="Trigger OTA Update" onclose={() => showOtaModal = false}>
        <div class="space-y-4">
          <div>
            <label for="ota-firmware-url" class="block text-2xs font-medium text-text-tertiary mb-1">Firmware URL</label>
            <input
              id="ota-firmware-url"
              type="url"
              bind:value={otaUrl}
              placeholder="https://example.com/firmware.bin"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
            <p class="text-[10px] text-text-tertiary mt-1">
              The device will download and install the firmware from this URL.
            </p>
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <button
              onclick={() => showOtaModal = false}
              class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
            >
              Cancel
            </button>
            <button
              onclick={triggerOta}
              disabled={submitting || !otaUrl}
              class="flex items-center gap-2 rounded-lg bg-warning px-4 py-2 text-sm font-medium text-white hover:bg-warning/90 disabled:opacity-50"
            >
              <Upload size={14} />
              {submitting ? 'Triggering...' : 'Start OTA'}
            </button>
          </div>
        </div>
      </Modal>
    {/if}
  {/if}
</div>
