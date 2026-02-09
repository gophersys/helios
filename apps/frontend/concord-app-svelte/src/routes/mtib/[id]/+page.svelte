<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { beforeNavigate } from '$app/navigation';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    ArrowLeft, Cpu, Zap, CircuitBoard, Terminal, Monitor,
    Loader2, Activity, WifiOff, ExternalLink, BarChart3,
    ChevronDown, ChevronUp
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import { LoadingState, ErrorAlert } from '$lib/components/ui';
  import { subscribeUart } from '$lib/services/websocket';
  import type { ApiResponse } from '$lib/types';
  import type { ObservabilitySnapshot } from '$lib/types/models';
  import type { ConcordNode } from '$lib/types/models';

  const auth = getAuth();

  /** Format raw revision string (e.g. "REV_1_2") → "1.2" */
  function fmtRev(raw: string | null | undefined): string | null {
    if (!raw) return null;
    const m = raw.match(/(\d+)[_.](\d+)/);
    return m ? `${m[1]}.${m[2]}` : raw;
  }

  interface NodeObservabilityResponse {
    node: { id: string; name: string; hostname: string; ipAddress: string | null };
    snapshot: ObservabilitySnapshot | null;
    lastUpdated: string | null;
    error: string | null;
  }

  interface PodInfo {
    name: string;
    nodeName: string;
    status: string;
    ready: boolean;
    restarts: number;
  }

  interface DeploymentStatus {
    name: string;
    replicas: number;
    readyReplicas: number;
    availableReplicas: number;
    pods: PodInfo[];
  }

  const nodeId = $derived($page.params.id);

  let data = $state<NodeObservabilityResponse | null>(null);
  let nodeDetail = $state<ConcordNode | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  const snapshot = $derived(data?.snapshot ?? null);
  const nodeInfo = $derived(data?.node ?? null);
  const isOnline = $derived(!!snapshot && !data?.error);
  const deployStatus = $derived(nodeDetail?.deploymentStatus as DeploymentStatus | null);

  // UART — always show these two physical ports
  const UART_PORTS = [
    { port_name: 'uart0', baud_rate: 115200 },
    { port_name: 'uart1', baud_rate: 115200 },
  ];

  const MAX_UART_LINES = 500;
  interface UartTerminal {
    lines: string[];
    live: boolean;
    connecting: boolean;
    error: string | null;
    unsubscribe: (() => void) | null;
  }
  let uartTerminals = $state<Record<string, UartTerminal>>({});
  let uartSubscribed = $state(false);
  let uartExpanded = $state<Record<string, boolean>>({});

  async function fetchData() {
    try {
      const [obsRes, nodeRes] = await Promise.all([
        apiFetch<ApiResponse<NodeObservabilityResponse>>(`/v2/mtibs/${nodeId}/observability`),
        apiFetch<ApiResponse<ConcordNode>>(`/v2/mtibs/${nodeId}`),
      ]);
      data = obsRes.data;
      nodeDetail = nodeRes.data;
      error = null;

      // Auto-subscribe to UART ports when snapshot first arrives
      if (obsRes.data?.snapshot && !uartSubscribed) {
        uartSubscribed = true;
        for (const port of UART_PORTS) {
          subscribeToUart(port.port_name, port.baud_rate);
        }
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to fetch observability data';
    } finally {
      loading = false;
    }
  }

  function subscribeToUart(portName: string, baud: number) {
    if (uartTerminals[portName]?.unsubscribe) return; // already subscribed
    if (!nodeId) return;

    uartTerminals[portName] = {
      lines: [],
      live: false,
      connecting: true,
      error: null,
      unsubscribe: null,
    };

    const currentNodeId = nodeId;
    const unsub = subscribeUart(
      { nodeId: currentNodeId, portName, baud },
      (rawData: string) => {
        const terminal = uartTerminals[portName];
        if (!terminal) return;
        // Split incoming data into lines, append to buffer
        const newLines = rawData.split('\n');
        const updated = [...terminal.lines, ...newLines];
        terminal.lines = updated.length > MAX_UART_LINES
          ? updated.slice(updated.length - MAX_UART_LINES)
          : updated;
        // Auto-scroll terminal to bottom
        tick().then(() => {
          const el = document.getElementById(`uart-${portName}`);
          if (el) el.scrollTop = el.scrollHeight;
        });
      },
      (message: string) => {
        const terminal = uartTerminals[portName];
        if (terminal) {
          terminal.error = message;
          terminal.live = false;
          terminal.connecting = false;
        }
      },
      () => {
        const terminal = uartTerminals[portName];
        if (terminal) {
          terminal.live = true;
          terminal.connecting = false;
        }
      },
    );

    uartTerminals[portName].unsubscribe = unsub;

    // Timeout: if still connecting after 10s, show error
    setTimeout(() => {
      const t = uartTerminals[portName];
      if (t && t.connecting) {
        t.connecting = false;
        t.error = 'Connection timed out — server may not support live UART streaming';
      }
    }, 10000);
  }

  function cleanupUart() {
    for (const terminal of Object.values(uartTerminals)) {
      terminal.unsubscribe?.();
    }
    uartTerminals = {};
    uartSubscribed = false;
  }

  function cleanup() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    cleanupUart();
  }

  onMount(() => {
    if (!auth.hasPermission('Concord.Admin.Nodes.View')) {
      goto('/');
      return;
    }
    fetchData();
    pollInterval = setInterval(fetchData, 2000);
  });

  onDestroy(() => {
    cleanup();
  });

  beforeNavigate(() => {
    cleanup();
  });

  function formatUptime(seconds: number): string {
    const s = Math.floor(seconds);
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  }

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function gpioDir(d: number): string {
    return d === 1 ? 'OUT' : 'IN';
  }

  function channelLabel(ch: number): string {
    if (ch === 0) return 'DUT Power';
    if (ch === 1) return 'DUT Charge';
    return `Ch ${ch}`;
  }

  /** Get K8s node name from deployment status pods */
  const k8sNodeName = $derived(
    deployStatus?.pods?.[0]?.nodeName ?? null
  );
</script>

<svelte:head>
  <title>{nodeInfo?.name || 'MTIB'} — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <!-- Header -->
  <div class="mb-6">
    <!-- Top row: back + deployment link -->
    <div class="flex items-center gap-2 mb-3">
      <button
        onclick={() => goto('/mtib')}
        class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} />
        MTIB
      </button>
      {#if deployStatus?.name}
        <span class="text-text-tertiary">/</span>
        <a
          href="/system/deployments/default/{deployStatus.name}"
          class="flex items-center gap-1 rounded-md bg-warning/15 border border-warning/30 px-2 py-0.5 text-2xs font-semibold text-warning hover:bg-warning/25 transition-colors"
        >
          <ExternalLink size={10} />
          Deployment
        </a>
      {/if}
    </div>

    <!-- Main header row -->
    {#if nodeInfo}
      <div class="flex items-center justify-between gap-4">
        <div class="flex items-center gap-3 min-w-0">
          <span class="relative flex h-3 w-3 shrink-0">
            <span class="h-3 w-3 rounded-full {isOnline ? 'bg-success' : 'bg-text-tertiary'}"></span>
            {#if isOnline}
              <span class="absolute inset-0 rounded-full bg-success animate-ping opacity-40"></span>
            {/if}
          </span>
          <div class="min-w-0">
            <h1 class="text-lg font-semibold text-text-primary truncate leading-tight">{nodeInfo.name}</h1>
            <div class="flex items-center gap-2 mt-0.5">
              {#if nodeInfo.ipAddress}
                <span class="text-2xs font-mono text-text-tertiary">{nodeInfo.ipAddress}</span>
              {/if}
              {#if snapshot?.system_metrics?.hardware_revision}
                <span class="rounded bg-surface-2 px-1.5 py-0.5 text-[9px] font-medium text-text-secondary">
                  REV {fmtRev(snapshot.system_metrics.hardware_revision)}
                </span>
              {/if}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-3 shrink-0">
          {#if isOnline}
            <span class="inline-flex items-center gap-1 rounded-full bg-success-muted px-2.5 py-1 text-2xs font-medium text-success">
              <Activity size={10} />
              Online
            </span>
          {:else if data?.error}
            <span class="inline-flex items-center gap-1 rounded-full bg-error-muted px-2.5 py-1 text-2xs font-medium text-error">
              <WifiOff size={10} />
              Offline
            </span>
          {/if}
          {#if data?.lastUpdated}
            <span class="text-2xs text-text-tertiary tabular-nums">
              {new Date(data.lastUpdated).toLocaleTimeString()}
            </span>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Connecting to MTIB..." />
  {:else if error && !data}
    <ErrorAlert message={error} />
  {:else if !snapshot}
    <!-- No snapshot yet (deploying or starting) -->
    {@const isConnErr = data?.error?.includes('UNAVAILABLE') || data?.error?.includes('Connection refused') || data?.error?.includes('failed to connect')}
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <div class="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-accent-muted">
        <Loader2 size={24} class="text-accent animate-spin" />
      </div>
      {#if isConnErr}
        <h2 class="text-sm font-semibold text-text-primary mb-1">Server Starting Up</h2>
        <p class="text-2xs text-text-tertiary max-w-md mb-4">The MTIB server is booting. This page will update automatically once it's ready.</p>
      {:else if data?.error}
        <h2 class="text-sm font-semibold text-text-primary mb-1">MTIB Server Not Ready</h2>
        <p class="text-2xs text-text-tertiary max-w-md mb-4">{data.error}</p>
      {:else}
        <h2 class="text-sm font-semibold text-text-primary mb-1">Waiting for Data</h2>
        <p class="text-2xs text-text-tertiary max-w-md mb-4">The MTIB server is starting up. Data will appear automatically.</p>
      {/if}
    </div>

    <!-- Pod / Deployment Status Card -->
    {#if deployStatus}
      <div class="max-w-xl mx-auto">
        <div class="card p-4">
          <div class="flex items-center gap-2 mb-3">
            <Cpu size={14} class="text-accent" />
            <h2 class="text-xs font-semibold text-text-primary uppercase tracking-wider">Deployment Status</h2>
            <span class="ml-auto text-2xs font-medium {deployStatus.readyReplicas > 0 ? 'text-success' : 'text-warning'}">
              {deployStatus.readyReplicas}/{deployStatus.replicas} ready
            </span>
          </div>

          <div class="grid grid-cols-2 gap-3 text-2xs mb-3">
            <div>
              <span class="text-text-tertiary">Deployment</span>
              <a href="/system/deployments/default/{deployStatus.name}"
                class="flex items-center gap-1 font-medium text-accent font-mono text-[11px] hover:underline">
                {deployStatus.name}
                <ExternalLink size={10} />
              </a>
            </div>
            <div>
              <span class="text-text-tertiary">Replicas</span>
              <p class="font-medium text-text-primary">
                {deployStatus.readyReplicas} ready / {deployStatus.replicas} desired
              </p>
            </div>
          </div>

          {#if deployStatus.pods && deployStatus.pods.length > 0}
            <div class="border-t border-border pt-3">
              <p class="text-2xs font-medium text-text-secondary mb-2">Pods</p>
              <div class="space-y-2">
                {#each deployStatus.pods as pod}
                  <a
                    href="/system/pods/default/{pod.name}"
                    class="flex items-center gap-3 rounded-lg bg-surface-1 px-3 py-2 hover:bg-surface-2 transition-colors cursor-pointer group"
                  >
                    <span class="h-2 w-2 rounded-full shrink-0
                      {pod.ready ? 'bg-success' :
                       pod.status === 'Running' ? 'bg-warning animate-pulse' :
                       pod.status === 'Pending' ? 'bg-text-tertiary animate-pulse' :
                       pod.status === 'ContainerCreating' ? 'bg-accent animate-pulse' :
                       'bg-error'}"></span>
                    <div class="flex-1 min-w-0">
                      <p class="text-2xs font-medium text-text-primary font-mono truncate group-hover:text-accent transition-colors">{pod.name}</p>
                      <p class="text-[10px] text-text-tertiary">Node: {pod.nodeName}</p>
                    </div>
                    <div class="flex items-center gap-2 shrink-0">
                      <span class="rounded-full px-2 py-0.5 text-[10px] font-medium
                        {pod.ready ? 'bg-success-muted text-success' :
                         pod.status === 'Running' ? 'bg-warning-muted text-warning' :
                         pod.status === 'Pending' ? 'bg-surface-2 text-text-tertiary' :
                         pod.status === 'ContainerCreating' ? 'bg-accent-muted text-accent' :
                         'bg-error-muted text-error'}">
                        {pod.status}
                      </span>
                      {#if pod.restarts > 0}
                        <span class="text-[10px] text-warning font-medium">{pod.restarts} restart{pod.restarts > 1 ? 's' : ''}</span>
                      {/if}
                      <ExternalLink size={12} class="text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </a>
                {/each}
              </div>
            </div>
          {:else}
            <div class="border-t border-border pt-3">
              <div class="flex items-center gap-2 text-2xs text-text-tertiary">
                <Loader2 size={12} class="animate-spin" />
                <span>Waiting for pod to be scheduled...</span>
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {:else}
    <!-- Main observability grid — compact -->
    <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">

      <!-- System Metrics (clickable → K8s node when available) -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <div
        onclick={() => k8sNodeName && goto(`/system/nodes/${k8sNodeName}`)}
        class="card px-3 py-2.5 {k8sNodeName ? 'hover:bg-surface-1 transition-colors cursor-pointer group' : ''}"
      >
        <div class="flex items-center gap-2 mb-2">
          <Monitor size={12} class="text-accent" />
          <h2 class="text-2xs font-semibold text-text-primary uppercase tracking-wider">System</h2>
          {#if snapshot.system_metrics}
            <div class="ml-auto flex items-center gap-1.5">
              {#if snapshot.system_metrics.hardware_revision}
                <span class="rounded bg-surface-2 px-1 py-px text-[9px] font-medium text-text-secondary">REV {fmtRev(snapshot.system_metrics.hardware_revision)}</span>
              {/if}
              {#if snapshot.system_metrics.server_version}
                <span class="rounded bg-surface-2 px-1 py-px text-[9px] font-medium text-text-secondary">v{snapshot.system_metrics.server_version}</span>
              {/if}
              {#if k8sNodeName}
                <ExternalLink size={9} class="text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
              {/if}
            </div>
          {/if}
        </div>

        {#if snapshot.system_metrics}
          {@const sm = snapshot.system_metrics}
          <div class="space-y-1.5">
            {#each [
              { label: 'CPU', value: sm.cpu_percent, color: 'bg-accent' },
              { label: 'Memory', value: sm.memory_percent, color: 'bg-info' },
              { label: 'Disk', value: sm.disk_percent, color: 'bg-warning' },
            ] as bar}
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-text-tertiary w-10 shrink-0">{bar.label}</span>
                <div class="flex-1 h-1 rounded-full bg-surface-2">
                  <div class="h-1 rounded-full transition-all duration-500 {bar.color}" style:width="{Math.min(bar.value, 100)}%"></div>
                </div>
                <span class="text-[10px] font-medium text-text-primary w-9 text-right tabular-nums">{bar.value.toFixed(1)}%</span>
              </div>
            {/each}
            <div class="text-[10px] text-text-tertiary">
              Uptime: <span class="font-medium text-text-secondary">{formatUptime(sm.uptime_seconds)}</span>
            </div>
          </div>
        {:else}
          <p class="text-2xs text-text-tertiary">No system metrics.</p>
        {/if}
      </div>

      <!-- Power -->
      <div class="card px-3 py-2.5">
        <div class="flex items-center gap-2 mb-2">
          <Zap size={12} class="text-warning" />
          <h2 class="text-2xs font-semibold text-text-primary uppercase tracking-wider">Power</h2>
          {#if snapshot.power_readings.length > 0}
            {@const totalPower = snapshot.power_readings.reduce((sum, r) => sum + r.power_mw, 0)}
            <span class="ml-auto text-xs font-bold text-warning tabular-nums">{totalPower.toFixed(1)}<span class="text-[9px] font-normal ml-0.5">mW</span></span>
          {/if}
        </div>

        {#if snapshot.power_readings.length > 0}
          <div class="divide-y divide-border">
            {#each snapshot.power_readings as pr, i}
              <div class="flex items-center gap-2 {i > 0 ? 'pt-2' : ''} {i < snapshot.power_readings.length - 1 ? 'pb-2' : ''}">
                <div class="flex items-center gap-1.5 w-20 shrink-0">
                  <span class="h-1.5 w-1.5 rounded-full {pr.enabled ? 'bg-success' : 'bg-text-tertiary'}"></span>
                  <span class="text-2xs font-semibold text-text-primary">{channelLabel(pr.channel)}</span>
                </div>
                <div class="flex-1 grid grid-cols-3 gap-1.5">
                  <div class="rounded bg-surface-1 px-2 py-1 text-center">
                    <p class="text-xs font-bold text-text-primary tabular-nums leading-none">{pr.voltage_v.toFixed(2)}</p>
                    <p class="text-[8px] text-text-tertiary mt-0.5">V</p>
                  </div>
                  <div class="rounded bg-surface-1 px-2 py-1 text-center">
                    <p class="text-xs font-bold text-text-primary tabular-nums leading-none">{pr.current_ma.toFixed(1)}</p>
                    <p class="text-[8px] text-text-tertiary mt-0.5">mA</p>
                  </div>
                  <div class="rounded bg-surface-1 px-2 py-1 text-center">
                    <p class="text-xs font-bold text-text-primary tabular-nums leading-none">{pr.power_mw.toFixed(1)}</p>
                    <p class="text-[8px] text-text-tertiary mt-0.5">mW</p>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-2xs text-text-tertiary">No power readings.</p>
        {/if}
      </div>

      <!-- ADC -->
      <div class="card px-3 py-2.5">
        <div class="flex items-center gap-2 mb-2">
          <BarChart3 size={12} class="text-accent" />
          <h2 class="text-2xs font-semibold text-text-primary uppercase tracking-wider">ADC</h2>
          {#if snapshot.adc_readings?.length > 0}
            <span class="ml-auto text-[10px] text-text-tertiary">{snapshot.adc_readings.length} ch</span>
          {/if}
        </div>

        {#if snapshot.adc_readings?.length > 0}
          <div class="grid grid-cols-4 gap-x-3 gap-y-0.5">
            {#each snapshot.adc_readings as adc}
              <div class="flex items-center justify-between py-0.5">
                <span class="text-[10px] font-medium text-text-tertiary">AN{adc.channel}</span>
                <span class="text-[10px] font-semibold text-text-primary tabular-nums">{adc.voltage_v.toFixed(3)}V</span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-2xs text-text-tertiary">No ADC readings.</p>
        {/if}
      </div>

      <!-- GPIO (pins 0-7) -->
      <div class="card px-3 py-2.5">
        <div class="flex items-center gap-2 mb-2">
          <CircuitBoard size={12} class="text-info" />
          <h2 class="text-2xs font-semibold text-text-primary uppercase tracking-wider">GPIO</h2>
          {#if snapshot.gpio_states.length > 0}
            {@const pins = snapshot.gpio_states.slice(0, 8)}
            {@const activeCount = pins.filter(g => g.value).length}
            <span class="ml-auto rounded-full bg-surface-2 px-1.5 py-px text-[9px] font-medium text-text-secondary">{activeCount} active</span>
          {/if}
        </div>

        {#if snapshot.gpio_states.length > 0}
          {@const pins = snapshot.gpio_states.slice(0, 8)}
          <div class="grid grid-cols-8 gap-1">
            {#each pins as gs}
              <div
                class="flex flex-col items-center rounded px-1 py-1 text-center {gs.value ? 'bg-success-muted' : 'bg-surface-1'}"
                title="Pin {gs.pin} | {gpioDir(gs.direction)} | {gs.value ? 'HIGH' : 'LOW'}"
              >
                <span class="text-[10px] font-semibold text-text-primary">{gs.pin}</span>
                <span class="h-1.5 w-1.5 rounded-full mt-0.5 {gs.value ? 'bg-success' : 'bg-text-tertiary'}"></span>
                <span class="text-[8px] mt-0.5 {gs.value ? 'text-success' : 'text-text-tertiary'}">{gpioDir(gs.direction)}</span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-2xs text-text-tertiary">No GPIO states.</p>
        {/if}
      </div>

      <!-- UART Terminals (full width, collapsible) -->
      {#each UART_PORTS as uartPort}
        {@const terminal = uartTerminals[uartPort.port_name]}
        {@const snapPort = snapshot.uart_ports.find(p => p.port_name === uartPort.port_name)}
        {@const expanded = uartExpanded[uartPort.port_name] ?? false}
        <div class="card overflow-hidden lg:col-span-2">
          <!-- Terminal header (clickable to expand/collapse) -->
          <button
            class="w-full flex items-center justify-between bg-surface-1 px-4 py-2 border-b border-border text-left"
            onclick={() => { uartExpanded[uartPort.port_name] = !expanded; }}
          >
            <div class="flex items-center gap-3">
              <Terminal size={14} class="text-success" />
              <span class="text-xs font-semibold text-text-primary">{uartPort.port_name}</span>
              <span class="text-2xs text-text-tertiary">{snapPort?.baud_rate ?? uartPort.baud_rate} baud</span>
            </div>
            <div class="flex items-center gap-3 text-2xs">
              {#if snapPort}
                <span class="text-text-tertiary tabular-nums">RX: {formatBytes(snapPort.bytes_received)}</span>
                <span class="text-text-tertiary tabular-nums">TX: {formatBytes(snapPort.bytes_sent)}</span>
              {/if}
              {#if terminal?.live}
                <span class="inline-flex items-center gap-1 rounded-full bg-success-muted px-1.5 py-0.5 text-[10px] font-semibold text-success">
                  <span class="relative flex h-1.5 w-1.5">
                    <span class="h-1.5 w-1.5 rounded-full bg-success"></span>
                    <span class="absolute inset-0 rounded-full bg-success animate-ping opacity-40"></span>
                  </span>
                  LIVE
                </span>
              {:else if terminal?.connecting}
                <span class="inline-flex items-center gap-1 rounded-full bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary">
                  <span class="h-1.5 w-1.5 rounded-full bg-text-tertiary animate-pulse"></span>
                  Connecting
                </span>
              {:else if terminal?.error}
                <span class="inline-flex items-center gap-1 rounded-full bg-error-muted px-1.5 py-0.5 text-[10px] font-medium text-error">
                  Error
                </span>
              {:else}
                <span class="inline-flex items-center gap-1 rounded-full bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-text-tertiary">
                  Idle
                </span>
              {/if}
              {#if expanded}
                <ChevronUp size={14} class="text-text-tertiary" />
              {:else}
                <ChevronDown size={14} class="text-text-tertiary" />
              {/if}
            </div>
          </button>

          {#if expanded}
            <!-- Terminal body -->
            <div class="h-64 overflow-y-auto bg-surface-0 p-3 font-mono text-[11px] leading-relaxed text-text-secondary scroll-smooth" id="uart-{uartPort.port_name}">
              {#if terminal?.lines && terminal.lines.length > 0}
                {#each terminal.lines as line}
                  <div class="whitespace-pre-wrap break-all">{line}</div>
                {/each}
              {:else if snapPort?.recent_lines && snapPort.recent_lines.length > 0}
                {#each snapPort.recent_lines as line}
                  <div class="whitespace-pre-wrap break-all">{line}</div>
                {/each}
              {:else}
                <div class="text-text-tertiary italic">No output</div>
              {/if}
            </div>

            {#if terminal?.error}
              <div class="bg-error-muted px-4 py-1.5 text-[10px] text-error">
                {terminal.error}
              </div>
            {/if}
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
