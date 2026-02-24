<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onMount, onDestroy } from 'svelte';
  import {
    ArrowLeft,
    Play,
    Square,
    Download,
    Settings,
    Loader2,
    CheckCircle2,
    AlertCircle,
  } from 'lucide-svelte';
  import { AnalyzerWaveformViewer } from '$lib/components/mtib';
  import { analyzerStore } from '$lib/stores/analyzer.svelte';
  import { ErrorAlert } from '$lib/components/ui';
  import { getAuth } from '$lib/stores/auth.svelte';

  const auth = getAuth();
  const { nodeId, captureId } = $derived($page.params);
  const isNewCapture = $derived(captureId === 'new');

  // Capture configuration
  let sampleRate = $state(10000000); // 10 MHz default
  let duration = $state(1.0); // 1 second
  let selectedChannels = $state<number[]>([0, 1, 2, 3, 4, 5, 6, 7]); // All channels

  // UI state
  let showConfig = $state(isNewCapture);
  let error = $state<string | null>(null);

  // Derived state from store
  const isCapturing = $derived(analyzerStore.isCapturing);
  const samplesCollected = $derived(analyzerStore.samplesCollected);
  const progressPercent = $derived(
    duration > 0 && sampleRate > 0
      ? Math.min(100, (samplesCollected / (sampleRate * duration)) * 100)
      : 0
  );

  onMount(() => {
    // Permission guard
    if (!auth.hasPermission('Concord.Admin.Nodes.View')) {
      goto('/');
      return;
    }

    if (!isNewCapture) {
      // Load existing capture
      // In a real implementation, we'd fetch the capture from the backend
      analyzerStore.connect(nodeId);
    }
  });

  onDestroy(() => {
    if (isCapturing) {
      analyzerStore.stop();
    }
    analyzerStore.disconnect();
  });

  async function startCapture() {
    error = null;
    try {
      await analyzerStore.start({
        sampleRate,
        duration,
        channels: selectedChannels,
      });
      showConfig = false;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to start capture';
    }
  }

  function stopCapture() {
    analyzerStore.stop();
  }

  function exportCsv() {
    analyzerStore.exportCsv(`analyzer-${nodeId}-${Date.now()}.csv`);
  }

  function exportVcd() {
    analyzerStore.exportVcd(`analyzer-${nodeId}-${Date.now()}.vcd`);
  }

  function toggleChannel(channel: number) {
    if (selectedChannels.includes(channel)) {
      selectedChannels = selectedChannels.filter((c) => c !== channel);
    } else {
      selectedChannels = [...selectedChannels, channel].sort();
    }
  }

  const sampleRateOptions = [
    { value: 1000000, label: '1 MHz' },
    { value: 5000000, label: '5 MHz' },
    { value: 10000000, label: '10 MHz' },
    { value: 20000000, label: '20 MHz' },
  ];

  const durationOptions = [
    { value: 0.1, label: '100 ms' },
    { value: 0.5, label: '500 ms' },
    { value: 1.0, label: '1 s' },
    { value: 2.0, label: '2 s' },
    { value: 5.0, label: '5 s' },
  ];
</script>

<svelte:head>
  <title>Logic Analyzer — {nodeId} — Concord</title>
</svelte:head>

<div class="animate-fade-in h-[calc(100vh-12rem)] flex flex-col">
  <!-- Controls Panel -->
  <div class="bg-surface-1 border-b border-surface-2 p-4 shrink-0">
    <div class="flex items-center justify-between gap-4">
      <!-- Left: Back button and status -->
      <div class="flex items-center gap-4">
        <button
          onclick={() => goto(`/mtib/${nodeId}`)}
          class="flex items-center gap-1 text-sm text-text-tertiary hover:text-text-primary transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </button>

        {#if isCapturing}
          <div class="flex items-center gap-2">
            <Loader2 size={16} class="text-accent animate-spin" />
            <span class="text-sm font-medium text-text-primary">Capturing...</span>
            <div class="ml-2 flex items-center gap-2">
              <div class="w-32 h-2 bg-surface-2 rounded-full overflow-hidden">
                <div
                  class="h-full bg-accent transition-all duration-300"
                  style="width: {progressPercent}%"
                ></div>
              </div>
              <span class="text-xs text-text-tertiary tabular-nums">
                {progressPercent.toFixed(1)}%
              </span>
            </div>
          </div>
        {:else if samplesCollected > 0}
          <div class="flex items-center gap-2">
            <CheckCircle2 size={16} class="text-success" />
            <span class="text-sm font-medium text-text-primary">
              {samplesCollected.toLocaleString()} samples
            </span>
          </div>
        {/if}
      </div>

      <!-- Right: Action buttons -->
      <div class="flex items-center gap-2">
        {#if !isCapturing && samplesCollected > 0}
          <button
            onclick={exportCsv}
            class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary hover:bg-surface-3 transition-colors"
          >
            <Download size={16} />
            Export CSV
          </button>
          <button
            onclick={exportVcd}
            class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary hover:bg-surface-3 transition-colors"
          >
            <Download size={16} />
            Export VCD
          </button>
        {/if}

        <button
          onclick={() => (showConfig = !showConfig)}
          class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm font-medium text-text-primary hover:bg-surface-3 transition-colors"
          disabled={isCapturing}
        >
          <Settings size={16} />
          Configure
        </button>

        {#if isCapturing}
          <button
            onclick={stopCapture}
            class="flex items-center gap-2 rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error-hover transition-colors"
          >
            <Square size={16} />
            Stop
          </button>
        {:else}
          <button
            onclick={startCapture}
            disabled={selectedChannels.length === 0}
            class="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Play size={16} />
            Start Capture
          </button>
        {/if}
      </div>
    </div>

    <!-- Configuration Panel (collapsible) -->
    {#if showConfig}
      <div class="mt-4 pt-4 border-t border-border">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <!-- Sample Rate -->
          <div>
            <label class="block text-xs font-medium text-text-secondary mb-2">
              Sample Rate
            </label>
            <div class="grid grid-cols-2 gap-2">
              {#each sampleRateOptions as option}
                <button
                  onclick={() => (sampleRate = option.value)}
                  disabled={isCapturing}
                  class="px-3 py-2 text-sm rounded-lg border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  class:border-accent={sampleRate === option.value}
                  class:bg-accent-muted={sampleRate === option.value}
                  class:text-accent={sampleRate === option.value}
                  class:border-surface-2={sampleRate !== option.value}
                  class:bg-surface-1={sampleRate !== option.value}
                  class:text-text-secondary={sampleRate !== option.value}
                >
                  {option.label}
                </button>
              {/each}
            </div>
          </div>

          <!-- Duration -->
          <div>
            <label class="block text-xs font-medium text-text-secondary mb-2">
              Duration
            </label>
            <div class="grid grid-cols-2 gap-2">
              {#each durationOptions as option}
                <button
                  onclick={() => (duration = option.value)}
                  disabled={isCapturing}
                  class="px-3 py-2 text-sm rounded-lg border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  class:border-accent={duration === option.value}
                  class:bg-accent-muted={duration === option.value}
                  class:text-accent={duration === option.value}
                  class:border-surface-2={duration !== option.value}
                  class:bg-surface-1={duration !== option.value}
                  class:text-text-secondary={duration !== option.value}
                >
                  {option.label}
                </button>
              {/each}
            </div>
          </div>

          <!-- Channel Selection -->
          <div>
            <label class="block text-xs font-medium text-text-secondary mb-2">
              Channels ({selectedChannels.length}/8)
            </label>
            <div class="grid grid-cols-4 gap-2">
              {#each Array(8) as _, i}
                <button
                  onclick={() => toggleChannel(i)}
                  disabled={isCapturing}
                  class="px-3 py-2 text-sm font-mono rounded-lg border transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  class:border-accent={selectedChannels.includes(i)}
                  class:bg-accent-muted={selectedChannels.includes(i)}
                  class:text-accent={selectedChannels.includes(i)}
                  class:border-surface-2={!selectedChannels.includes(i)}
                  class:bg-surface-1={!selectedChannels.includes(i)}
                  class:text-text-tertiary={!selectedChannels.includes(i)}
                  aria-pressed={selectedChannels.includes(i)}
                >
                  {i}
                </button>
              {/each}
            </div>
          </div>
        </div>

        {#if selectedChannels.length === 0}
          <div class="mt-3 flex items-center gap-2 text-xs text-warning">
            <AlertCircle size={14} />
            Please select at least one channel
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Error Display -->
  {#if error}
    <div class="p-4 shrink-0">
      <ErrorAlert message={error} />
    </div>
  {/if}

  <!-- Waveform Viewer (full height) -->
  <div class="flex-1 min-h-0 bg-surface-0">
    {#if samplesCollected > 0}
      <AnalyzerWaveformViewer />
    {:else if !isCapturing}
      <div class="h-full flex items-center justify-center">
        <div class="text-center">
          <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-accent-muted mx-auto">
            <Play size={32} class="text-accent" />
          </div>
          <h2 class="text-lg font-semibold text-text-primary mb-2">
            No Capture Data
          </h2>
          <p class="text-sm text-text-secondary max-w-sm">
            Configure your capture settings and click "Start Capture" to begin recording logic analyzer data.
          </p>
        </div>
      </div>
    {/if}
  </div>
</div>
