<script lang="ts">
  import { onDestroy } from 'svelte';
  import { Play, Pause, RotateCcw, ExternalLink } from 'lucide-svelte';
  import FlowCanvas from '$lib/components/validation/flow-canvas.svelte';
  import StepDetailPanel from '$lib/components/validation/step-detail-panel.svelte';
  import BuildDetailPanel from '$lib/components/validation/build-detail-panel.svelte';
  import type { FlowNodeData, ValidationStep } from '$lib/components/validation/types';
  import {
    MOCK_NODES,
    MOCK_EDGES,
    MOCK_STEPS,
    MOCK_BUILDS,
    MOCK_BUILD_ARTIFACTS,
    MOCK_BUILD_LOGS,
    simulateFuotaProgress,
  } from '$lib/components/validation/mock-data';

  // Clone mock data so we can mutate it
  let nodes = $state<FlowNodeData[]>(JSON.parse(JSON.stringify(MOCK_NODES)));
  let steps = $state<Record<string, ValidationStep>>(JSON.parse(JSON.stringify(MOCK_STEPS)));

  let selectedNodeId = $state<string | null>(null);
  let selectedStep = $derived(selectedNodeId ? steps[selectedNodeId] : null);
  let selectedNode = $derived(selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) : null);

  let isSimulating = $state(false);
  let stopSimulation: (() => void) | null = null;

  // Run info
  const runInfo = {
    id: 'cmmx_alpha_stage4_demo',
    designName: 'Alpha B0 Full Validation',
    pipelineId: 'cmmk9o8zh00008785xh9ltn0d',
    deviceId: '70B3D584C01E1FCC',
    nodeId: 'MTIB-REV1.2 (10.4.45.33)',
    startedAt: '2026-03-10T18:00:00Z',
    status: 'RUNNING',
  };

  function startSimulation() {
    if (isSimulating) return;
    isSimulating = true;

    // Find FUOTA node and simulate progress
    const fuotaNode = nodes.find((n) => n.id === 'fuota_mfg');
    if (!fuotaNode || fuotaNode.status !== 'RUNNING') return;

    stopSimulation = simulateFuotaProgress(fuotaNode.progress ?? 67, (progress, pages, total) => {
      // Update node
      const idx = nodes.findIndex((n) => n.id === 'fuota_mfg');
      if (idx >= 0) {
        nodes[idx] = {
          ...nodes[idx],
          progress,
          summary: `${pages}/${total}`,
          status: progress >= 100 ? 'PASSED' : 'RUNNING',
        };
        nodes = [...nodes]; // trigger reactivity
      }

      // Update step
      if (steps.fuota_mfg) {
        steps.fuota_mfg = {
          ...steps.fuota_mfg,
          fuotaPages: pages,
          fuotaPercent: progress,
          status: progress >= 100 ? 'PASSED' : 'RUNNING',
          summary: `${progress}% (${pages}/${total})`,
        };
        steps = { ...steps };
      }

      // When FUOTA completes, advance to next step
      if (progress >= 100) {
        isSimulating = false;

        // Mark next steps as ready
        setTimeout(() => {
          const post2Idx = nodes.findIndex((n) => n.id === 'post_2');
          if (post2Idx >= 0) {
            nodes[post2Idx] = { ...nodes[post2Idx], status: 'RUNNING' };
            nodes = [...nodes];

            if (steps.post_2) {
              steps.post_2 = { ...steps.post_2, status: 'RUNNING' };
              steps = { ...steps };
            }
          }
        }, 1000);
      }
    });
  }

  function pauseSimulation() {
    if (stopSimulation) {
      stopSimulation();
      stopSimulation = null;
    }
    isSimulating = false;
  }

  function resetSimulation() {
    pauseSimulation();
    nodes = JSON.parse(JSON.stringify(MOCK_NODES));
    steps = JSON.parse(JSON.stringify(MOCK_STEPS));
    selectedNodeId = null;
  }

  function handleNodeClick(id: string) {
    selectedNodeId = id;
  }

  function formatTime(iso: string | undefined): string {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  }

  onDestroy(() => {
    pauseSimulation();
  });
</script>

<svelte:head>
  <title>Validation Flow - Concord</title>
</svelte:head>

<div class="animate-fade-in space-y-4">
  <!-- Header -->
  <div class="flex items-start justify-between gap-4">
    <div>
      <h1 class="text-lg font-semibold">{runInfo.designName}</h1>
      <div class="mt-1 flex items-center gap-4 text-xs text-text-tertiary">
        <span>Run: {runInfo.id}</span>
        <span>Device: {runInfo.deviceId}</span>
        <span>Node: {runInfo.nodeId}</span>
      </div>
    </div>

    <div class="flex items-center gap-3">
      <!-- Status badge -->
      <span
        class="rounded-full px-3 py-1 text-sm font-medium
        {runInfo.status === 'RUNNING'
          ? 'bg-accent/20 text-accent'
          : runInfo.status === 'PASSED'
            ? 'bg-success/20 text-success'
            : 'bg-error/20 text-error'}"
      >
        {runInfo.status}
      </span>

      <!-- Simulation controls -->
      <div class="flex gap-1 rounded-lg bg-surface-1 p-1">
        {#if isSimulating}
          <button
            type="button"
            class="flex items-center gap-1 rounded px-3 py-1.5 text-sm hover:bg-surface-2"
            onclick={pauseSimulation}
          >
            <Pause class="h-4 w-4" />
            Pause
          </button>
        {:else}
          <button
            type="button"
            class="flex items-center gap-1 rounded px-3 py-1.5 text-sm hover:bg-surface-2"
            onclick={startSimulation}
          >
            <Play class="h-4 w-4" />
            Simulate
          </button>
        {/if}
        <button
          type="button"
          class="flex items-center gap-1 rounded px-3 py-1.5 text-sm hover:bg-surface-2"
          onclick={resetSimulation}
        >
          <RotateCcw class="h-4 w-4" />
          Reset
        </button>
      </div>

      <!-- Link to pipeline -->
      <a
        href="/ci/pipelines/{runInfo.pipelineId}"
        class="flex items-center gap-1 rounded bg-surface-1 px-3 py-1.5 text-sm hover:bg-surface-2"
      >
        <ExternalLink class="h-4 w-4" />
        Pipeline
      </a>
    </div>
  </div>

  <!-- Progress summary cards -->
  <div class="grid grid-cols-3 gap-3">
    <div class="card card-sm">
      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Started</div>
      <div class="mt-1 text-sm font-semibold">{formatTime(runInfo.startedAt)}</div>
    </div>
    <div class="card card-sm">
      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Steps</div>
      <div class="mt-1 text-sm font-semibold">
        <span class="text-success">{nodes.filter((n) => n.status === 'PASSED').length}</span>
        <span class="text-text-tertiary"> / {nodes.length}</span>
      </div>
    </div>
    <div class="card card-sm">
      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Current Step</div>
      <div class="mt-1 text-sm font-semibold text-accent">
        {nodes.find((n) => n.status === 'RUNNING')?.label ?? 'None'}
      </div>
    </div>
  </div>

  <!-- Main content: Canvas + Detail Panel -->
  <div class="flex gap-4" style="min-height: 500px;">
    <!-- Canvas -->
    <div class="flex-1">
      <FlowCanvas {nodes} edges={MOCK_EDGES} bind:selectedNodeId onNodeClick={handleNodeClick} />
    </div>

    <!-- Detail panel (right side, half screen minimum) -->
    {#if selectedNode}
      <div class="w-1/2 min-w-[500px] flex-shrink-0 h-full rounded-lg border border-surface-2 overflow-hidden">
        <!-- Debug: node.id={selectedNode.id} node.type={selectedNode.type} -->
        {#if selectedNode.id === 'build'}
          <BuildDetailPanel
            builds={MOCK_BUILDS}
            artifacts={MOCK_BUILD_ARTIFACTS}
            logs={MOCK_BUILD_LOGS}
            pipelineId={runInfo.pipelineId}
            onclose={() => (selectedNodeId = null)}
          />
        {:else if selectedStep}
          <StepDetailPanel step={selectedStep} onclose={() => (selectedNodeId = null)} />
        {/if}
      </div>
    {/if}
  </div>
</div>
