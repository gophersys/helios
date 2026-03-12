<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { RefreshCw, Plus, Activity, WifiOff, Radio, Cpu, Check } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch, api } from '$lib/api';
  import { PageHeader, ErrorAlert, EmptyState, LoadingState, Select } from '$lib/components/ui';
  import { DeviceCard } from '$lib/components/icle';
  import type { IcleDevice, DiscoveredIcleDevice, IcleDiscoveryResult } from '$lib/types/icle';
  import type { ApiResponse } from '$lib/types';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('devices:manage'));

  let devices = $state<IcleDevice[]>([]);
  let discoveredDevices = $state<DiscoveredIcleDevice[]>([]);
  let loading = $state(true);
  let syncing = $state(false);
  let error = $state<string | null>(null);
  let submitting = $state(false);

  // Registration form state
  let registeringDevice = $state<DiscoveredIcleDevice | null>(null);
  let registerName = $state('');

  // Auto-refresh
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  const POLL_MS = 10_000;

  // Sort: online first, then logging, then offline
  const sortedDevices = $derived(
    [...devices].sort((a, b) => {
      const order: Record<string, number> = { LOGGING: 0, ONLINE: 1, CONFIG: 2, BOOT: 3, OTA: 4, OFFLINE: 5 };
      const diff = (order[a.status] ?? 5) - (order[b.status] ?? 5);
      if (diff !== 0) return diff;
      return (a.name || a.deviceId).localeCompare(b.name || b.deviceId);
    })
  );

  async function fetchDevices() {
    try {
      const res = await apiFetch<ApiResponse<{ devices: IcleDevice[] }>>('/v2/devices/icle');
      devices = res.data?.devices || [];
    } catch (err) {
      if (devices.length === 0) {
        error = err instanceof Error ? err.message : 'Failed to load devices';
      }
    }
  }

  async function handleDiscover() {
    error = null;
    syncing = true;
    try {
      const res = await api.post<ApiResponse<IcleDiscoveryResult>>('/v2/devices/icle/discover');
      const result = res.data;
      discoveredDevices = result.discovered || [];
      await fetchDevices();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Discovery failed';
    } finally {
      syncing = false;
    }
  }

  async function initialLoad() {
    await fetchDevices();
    loading = false;
    await handleDiscover();
  }

  onMount(() => {
    if (!auth.hasPermission('devices:view')) {
      goto('/');
      return;
    }
    initialLoad();
    pollTimer = setInterval(fetchDevices, POLL_MS);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  // Registration
  function startRegister(device: DiscoveredIcleDevice) {
    registeringDevice = device;
    registerName = device.deviceId;
  }

  function cancelRegister() {
    registeringDevice = null;
    registerName = '';
  }

  async function handleRegister() {
    if (!registeringDevice) return;
    error = null;
    submitting = true;
    try {
      await api.post('/v2/devices/icle', {
        deviceId: registeringDevice.deviceId,
        name: registerName || null,
        ipAddress: registeringDevice.ipAddress,
        macAddress: registeringDevice.macAddress,
        firmwareVersion: registeringDevice.firmwareVersion,
      });
      discoveredDevices = discoveredDevices.filter(d => d.deviceId !== registeringDevice!.deviceId);
      cancelRegister();
      await fetchDevices();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to register device';
    } finally {
      submitting = false;
    }
  }

  function handleDeviceClick(device: IcleDevice) {
    goto(`/icle/${device.id}`);
  }

  function handleDiscoveredClick(device: DiscoveredIcleDevice) {
    if (canManage) {
      startRegister(device);
    }
  }

  function getStatusCounts() {
    const counts = { online: 0, logging: 0, offline: 0 };
    for (const d of devices) {
      if (d.status === 'LOGGING') counts.logging++;
      else if (d.status === 'OFFLINE') counts.offline++;
      else counts.online++;
    }
    return counts;
  }

  const statusCounts = $derived(getStatusCounts());
</script>

<svelte:head>
  <title>ICLE Devices - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="ICLE Devices"
      description="Manage ICLE current loggers and power monitors."
    >
      {#snippet actions()}
        {#if canManage}
          <button
            onclick={handleDiscover}
            disabled={syncing}
            class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary hover:bg-surface-3 disabled:opacity-50"
          >
            <RefreshCw size={16} class={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Scanning...' : 'Scan Network'}
          </button>
        {/if}
      {/snippet}
    </PageHeader>
  </div>

  {#if loading}
    <LoadingState message="Loading ICLE devices..." />
  {:else}
    <ErrorAlert message={error} />

    <!-- Status Summary -->
    {#if devices.length > 0}
      <div class="mb-6 flex items-center gap-4">
        <div class="flex items-center gap-1.5">
          <span class="h-2 w-2 rounded-full bg-success"></span>
          <span class="text-xs text-text-secondary">{statusCounts.online} Online</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="h-2 w-2 rounded-full bg-accent animate-pulse"></span>
          <span class="text-xs text-text-secondary">{statusCounts.logging} Logging</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="h-2 w-2 rounded-full bg-text-tertiary"></span>
          <span class="text-xs text-text-secondary">{statusCounts.offline} Offline</span>
        </div>
      </div>
    {/if}

    <!-- Discovered Devices (unregistered) -->
    {#if discoveredDevices.length > 0}
      <div class="mb-6">
        <div class="mb-2 flex items-center gap-2">
          <span class="h-2 w-2 rounded-full bg-accent animate-pulse"></span>
          <h2 class="text-xs font-semibold text-text-primary uppercase tracking-wider">Discovered</h2>
          <span class="rounded-full bg-accent-muted px-1.5 py-0.5 text-[10px] font-medium text-accent">
            {discoveredDevices.length}
          </span>
        </div>
        <div class="space-y-1.5">
          {#each discoveredDevices as device (device.deviceId)}
            {#if registeringDevice?.deviceId === device.deviceId}
              <!-- Registration form -->
              <div class="rounded-lg border border-accent bg-accent-muted px-4 py-3">
                <div class="flex items-center justify-between gap-4">
                  <div class="flex-1 min-w-0">
                    <p class="text-xs font-medium text-text-primary font-mono">{device.deviceId}</p>
                    <p class="text-[10px] text-text-tertiary">{device.ipAddress}</p>
                  </div>
                  <div class="flex items-center gap-2">
                    <input
                      type="text"
                      bind:value={registerName}
                      placeholder="Device name (optional)"
                      class="w-40 rounded-lg border border-border bg-surface-0 px-2 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                    />
                    <button
                      onclick={handleRegister}
                      disabled={submitting}
                      class="flex items-center gap-1 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                    >
                      <Check size={12} />
                      {submitting ? '...' : 'Register'}
                    </button>
                    <button
                      onclick={cancelRegister}
                      class="rounded-lg px-2 py-1.5 text-xs text-text-secondary hover:bg-surface-2"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            {:else}
              <!-- Discovered device row -->
              <button
                onclick={() => handleDiscoveredClick(device)}
                class="flex w-full items-center justify-between rounded-lg border border-border bg-surface-1 px-4 py-2.5 text-left hover:bg-surface-2 transition-colors"
              >
                <div class="flex items-center gap-3">
                  <Cpu size={14} class="text-text-tertiary" />
                  <div>
                    <span class="text-xs font-medium text-text-primary font-mono">{device.deviceId}</span>
                    <div class="flex items-center gap-2 mt-0.5">
                      <span class="text-[10px] text-text-tertiary">{device.ipAddress}</span>
                      {#if device.firmwareVersion}
                        <span class="text-[10px] text-text-tertiary">v{device.firmwareVersion}</span>
                      {/if}
                    </div>
                  </div>
                </div>
                {#if canManage}
                  <div class="flex items-center gap-1 text-[10px] font-medium text-accent">
                    <Plus size={12} /> Register
                  </div>
                {/if}
              </button>
            {/if}
          {/each}
        </div>
      </div>
    {/if}

    <!-- Registered Devices Grid -->
    {#if devices.length > 0}
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {#each sortedDevices as device (device.id)}
          <DeviceCard {device} onclick={() => handleDeviceClick(device)} />
        {/each}
      </div>
    {:else if discoveredDevices.length === 0}
      <EmptyState message="No ICLE devices found. Click 'Scan Network' to discover devices." />
    {/if}
  {/if}
</div>
