<script lang="ts">
  import { onMount } from 'svelte';
  import FlowNode from './flow-node.svelte';
  import FlowEdge from './flow-edge.svelte';
  import type { FlowNodeData, FlowEdgeData, ValidationStepStatus } from './types';

  let {
    nodes = [],
    edges = [],
    selectedNodeId = $bindable<string | null>(null),
    onNodeClick = (_id: string) => {},
  }: {
    nodes: FlowNodeData[];
    edges: FlowEdgeData[];
    selectedNodeId?: string | null;
    onNodeClick?: (id: string) => void;
  } = $props();

  let canvasEl: HTMLDivElement;
  let scale = $state(1);
  let translateX = $state(0);
  let translateY = $state(0);

  // Calculate node positions in a horizontal flow layout
  function getNodePositions(nodes: FlowNodeData[], edges: FlowEdgeData[]) {
    const positions: Record<string, { x: number; y: number }> = {};
    const nodeWidth = 160;
    const nodeHeight = 80;
    const gapX = 60;
    const gapY = 40;
    const startX = 40;
    const startY = 60;

    // Build adjacency list
    const children: Record<string, string[]> = {};
    const parents: Record<string, string[]> = {};
    nodes.forEach((n) => {
      children[n.id] = [];
      parents[n.id] = [];
    });
    edges.forEach((e) => {
      children[e.source]?.push(e.target);
      parents[e.target]?.push(e.source);
    });

    // Find root nodes (no parents)
    const roots = nodes.filter((n) => parents[n.id].length === 0);

    // BFS to assign columns
    const columns: Record<string, number> = {};
    const visited = new Set<string>();
    const queue: { id: string; col: number }[] = roots.map((n) => ({ id: n.id, col: 0 }));

    while (queue.length > 0) {
      const { id, col } = queue.shift()!;
      if (visited.has(id)) continue;
      visited.add(id);
      columns[id] = Math.max(columns[id] ?? 0, col);

      for (const child of children[id]) {
        queue.push({ id: child, col: col + 1 });
      }
    }

    // Group by column
    const byColumn: Record<number, string[]> = {};
    for (const [id, col] of Object.entries(columns)) {
      byColumn[col] = byColumn[col] || [];
      byColumn[col].push(id);
    }

    // Assign positions
    for (const [colStr, ids] of Object.entries(byColumn)) {
      const col = parseInt(colStr);
      ids.forEach((id, row) => {
        positions[id] = {
          x: startX + col * (nodeWidth + gapX),
          y: startY + row * (nodeHeight + gapY),
        };
      });
    }

    return positions;
  }

  let positions = $derived(getNodePositions(nodes, edges));

  function handleWheel(e: WheelEvent) {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      scale = Math.max(0.5, Math.min(2, scale * delta));
    }
  }

  function handleNodeSelect(id: string) {
    selectedNodeId = id;
    onNodeClick(id);
  }
</script>

<div
  bind:this={canvasEl}
  class="relative w-full overflow-hidden rounded-lg border border-surface-2 bg-surface-0"
  style="height: 100%; min-height: 500px;"
  onwheel={handleWheel}
>
  <!-- Dotted grid background -->
  <div
    class="pointer-events-none absolute inset-0"
    style="
      background-image: radial-gradient(circle, var(--color-surface-2) 1px, transparent 1px);
      background-size: 20px 20px;
    "
  ></div>

  <!-- Transform container -->
  <div
    class="absolute inset-0"
    style="transform: translate({translateX}px, {translateY}px) scale({scale}); transform-origin: 0 0;"
  >
    <!-- Edges (SVG layer) -->
    <svg class="pointer-events-none absolute inset-0 h-[2000px] w-[2000px]">
      {#each edges as edge}
        {@const sourcePos = positions[edge.source]}
        {@const targetPos = positions[edge.target]}
        {#if sourcePos && targetPos}
          <FlowEdge
            x1={sourcePos.x + 160}
            y1={sourcePos.y + 40}
            x2={targetPos.x}
            y2={targetPos.y + 40}
          />
        {/if}
      {/each}
    </svg>

    <!-- Nodes -->
    {#each nodes as node}
      {@const pos = positions[node.id]}
      {#if pos}
        <div class="absolute" style="left: {pos.x}px; top: {pos.y}px;">
          <FlowNode
            {node}
            selected={selectedNodeId === node.id}
            onclick={() => handleNodeSelect(node.id)}
          />
        </div>
      {/if}
    {/each}
  </div>

  <!-- Legend -->
  <div class="absolute bottom-3 left-3 flex gap-3 rounded bg-surface-1/90 px-3 py-2 text-xs">
    <span class="flex items-center gap-1">
      <span class="h-2 w-2 rounded-full bg-text-tertiary"></span> Pending
    </span>
    <span class="flex items-center gap-1">
      <span class="h-2 w-2 animate-pulse rounded-full bg-accent"></span> Running
    </span>
    <span class="flex items-center gap-1">
      <span class="h-2 w-2 rounded-full bg-success"></span> Passed
    </span>
    <span class="flex items-center gap-1">
      <span class="h-2 w-2 rounded-full bg-error"></span> Failed
    </span>
    <span class="flex items-center gap-1">
      <span class="h-2 w-2 rounded-full bg-warning"></span> Skipped
    </span>
  </div>

  <!-- Zoom controls -->
  <div class="absolute bottom-3 right-3 flex gap-1">
    <button
      class="rounded bg-surface-1 px-2 py-1 text-sm hover:bg-surface-2"
      onclick={() => (scale = Math.min(2, scale * 1.2))}
    >
      +
    </button>
    <button
      class="rounded bg-surface-1 px-2 py-1 text-sm hover:bg-surface-2"
      onclick={() => (scale = Math.max(0.5, scale / 1.2))}
    >
      -
    </button>
    <button
      class="rounded bg-surface-1 px-2 py-1 text-sm hover:bg-surface-2"
      onclick={() => {
        scale = 1;
        translateX = 0;
        translateY = 0;
      }}
    >
      Reset
    </button>
  </div>
</div>
