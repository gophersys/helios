<script lang="ts">
  import { Loader2 } from 'lucide-svelte';
  import ResizeLayout from '$lib/components/validation/resize-layout.svelte';
  import { type SlotContext, setSlotContext } from './slot-context.svelte';
  import SlotHeader from './slot-header.svelte';
  import SlotStageSidebar from './slot-stage-sidebar.svelte';
  import SlotTestList from './slot-test-list.svelte';
  import SlotChartPanel from './slot-chart-panel.svelte';
  import SlotUartPanel from './slot-uart-panel.svelte';

  let {
    slot,
    productName = '',
    boardRevision = '',
    firmwareVersion = '',
    slotLabel = '',
    socLabels = [],
    isLive = false,
    showHeader = true,
  }: {
    slot: SlotContext;
    productName?: string;
    boardRevision?: string;
    firmwareVersion?: string;
    slotLabel?: string;
    socLabels?: string[];
    isLive?: boolean;
    showHeader?: boolean;
  } = $props();

  // Provide SlotContext to all children via Svelte context
  setSlotContext(slot);

  // Escape key: clear time range selection
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && slot.selectedRange) {
      slot.selectedRange = null;
      slot.autoFollow = true;
      e.preventDefault();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if !slot.hydrated}
  <div class="flex items-center justify-center h-64">
    <div class="flex flex-col items-center gap-3">
      <Loader2 size={28} class="text-accent animate-spin" />
      <span class="text-sm text-text-secondary font-medium">Loading slot data...</span>
    </div>
  </div>
{:else if slot.liveTests.length > 0}
  {#if showHeader}
    <SlotHeader {productName} {boardRevision} {firmwareVersion} {slotLabel} {isLive} />
  {/if}

  <div class="flex flex-col relative" style="height: calc(100vh - 160px);">
    <!-- Telemetry loading overlay -->
    {#if slot.telemetryLoading && slot.analysisMode}
      <div class="absolute inset-0 z-20 flex items-center justify-center bg-surface-0/60 backdrop-blur-xs rounded-lg">
        <div class="flex flex-col items-center gap-3">
          <Loader2 size={28} class="text-accent animate-spin" />
          <span class="text-sm text-text-secondary font-medium">Loading telemetry data...</span>
        </div>
      </div>
    {/if}

    <!-- Top row: stages + tests + charts -->
    <div class="flex overflow-hidden" style="flex: 0 0 {slot.topPanelHeight}%;">
      <!-- Stage sidebar -->
      <div class="shrink-0 overflow-y-auto" style="width: {slot.sidebarWidth}px;">
        <SlotStageSidebar />
      </div>

      <!-- Vertical resize: sidebar ↔ test list -->
      <ResizeLayout
        orientation="horizontal"
        initialSize={192}
        minSize={120}
        maxSize={400}
        bind:size={slot.sidebarWidth}
        bind:resizing={slot.vResizing as any}
      />

      <!-- Center: test list -->
      <div class="flex-1 min-w-0 overflow-y-auto">
        <SlotTestList />
      </div>

      <!-- Vertical resize: test list ↔ charts (xl only) -->
      <div class="hidden xl:flex">
        <ResizeLayout
          orientation="horizontal"
          initialSize={576}
          minSize={300}
          maxSize={800}
          inverted={true}
          bind:size={slot.chartsWidth}
          bind:resizing={slot.vResizing as any}
        />
      </div>

      <!-- Charts (right side, xl+ only) -->
      <div class="shrink-0 hidden xl:flex flex-col gap-2" style="width: {slot.chartsWidth}px;">
        <SlotChartPanel />
      </div>
    </div>

    <!-- Horizontal resize: top ↔ UART -->
    <ResizeLayout
      orientation="vertical"
      initialSize={50}
      minSize={15}
      maxSize={80}
      bind:size={slot.topPanelHeight}
      bind:resizing={slot.resizing}
    />

    <!-- UART terminals (full-width bottom) -->
    <div class="flex-1 min-h-0 overflow-hidden">
      <SlotUartPanel {socLabels} />
    </div>
  </div>
{:else}
  <div class="flex items-center justify-center h-64 text-text-tertiary text-sm">
    No test executions yet. Waiting for test runner...
  </div>
{/if}
