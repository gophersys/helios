<script lang="ts">
  // The Service Map lens — the kept Svelte Flow graph, refined: Eden LIGHT theme (token-driven, no
  // tokyo-night), meaningful edges only (routes + depends by default; selects/mounts opt-in),
  // scope-first (a drilled-in namespace renders alone), focus+context fade on select, and the shared
  // Detail drawer (no inline panel). It projects the same model every other lens reads.
  import { onMount } from 'svelte';
  import { SvelteFlow, Background, Controls, MiniMap } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import ServiceNode from './ServiceNode.svelte';
  import NsGroup from './NsGroup.svelte';
  import { buildFlow } from './layout';
  import { clusters } from './clustersState.svelte';
  import type { ClusterModel } from './model';
  import type { EdgeKind } from './contract';

  let { model }: { model: ClusterModel } = $props();

  let nodes = $state.raw<ReturnType<typeof buildFlow>['nodes']>([]);
  let edges = $state.raw<ReturnType<typeof buildFlow>['edges']>([]);
  $effect(() => {
    const f = buildFlow(model.topo, {
      edgeKinds: clusters.mapEdges,
      scope: clusters.namespaces,
      focusId: clusters.focusId,
    });
    nodes = f.nodes;
    edges = f.edges;
  });

  const nodeTypes = { service: ServiceNode, nsgroup: NsGroup } as never;

  function onNodeClick(e: { node?: { data?: { node?: { id: string } } } }) {
    const id = e?.node?.data?.node?.id;
    if (id) clusters.focus(id);
  }

  const EDGE_TOGGLES: { kind: EdgeKind; label: string }[] = [
    { kind: 'routes', label: 'routes' },
    { kind: 'depends', label: 'depends' },
    { kind: 'selects', label: 'selects' },
    { kind: 'mounts', label: 'mounts' },
  ];

  // MiniMap/Background render to SVG/canvas where CSS vars don't resolve — read the generated tokens
  // once so even those stay theme-derived rather than hardcoded.
  let mm = $state({ outline: '#9aa', primary: '#4a6' });
  onMount(() => {
    const cs = getComputedStyle(document.documentElement);
    mm = {
      outline: cs.getPropertyValue('--color-outline').trim() || mm.outline,
      primary: cs.getPropertyValue('--color-primary').trim() || mm.primary,
    };
  });

  const scoped = $derived([...clusters.namespaces]);
</script>

<div class="wrap">
  <div class="bar">
    <div class="left">
      {#if scoped.length}
        <span class="scope">
          scoped: {scoped.join(', ')}
          <button onclick={() => (clusters.namespaces = new Set())}>view entire cluster ✕</button>
        </span>
      {:else}
        <span class="hint">{model.members.length} resources · click a node to inspect</span>
      {/if}
    </div>
    <div class="toggles">
      <span class="tlabel">edges</span>
      {#each EDGE_TOGGLES as t}
        <button class="tg" class:on={clusters.mapEdges.has(t.kind)} onclick={() => clusters.toggleEdge(t.kind)}>
          {t.label}
        </button>
      {/each}
    </div>
  </div>

  <div class="flow">
    <SvelteFlow
      bind:nodes
      bind:edges
      {nodeTypes}
      colorMode="light"
      fitView
      minZoom={0.15}
      nodesDraggable={false}
      nodesConnectable={false}
      onnodeclick={onNodeClick}
      onpaneclick={() => clusters.focus(null)}
    >
      <Background gap={20} bgColor="var(--eden-app-bg)" patternColor={mm.outline} />
      <Controls showLock={false} />
      <MiniMap pannable zoomable nodeColor={mm.outline} maskColor="color-mix(in oklab, var(--eden-app-bg) 65%, transparent)" />
    </SvelteFlow>
  </div>
</div>

<style>
  .wrap {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 14px;
    border-bottom: 1px solid var(--eden-app-line);
    background: var(--eden-app-panel-bg);
    flex-wrap: wrap;
  }
  .hint {
    color: var(--eden-app-muted);
    font-size: 12px;
  }
  .scope {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--eden-app-fg);
  }
  .scope button {
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 7px;
    padding: 3px 8px;
    font: inherit;
    font-size: 11px;
    color: var(--eden-app-muted);
    cursor: pointer;
  }
  .toggles {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .tlabel {
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--eden-app-muted);
    margin-inline-end: 2px;
  }
  .tg {
    background: var(--eden-app-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: 999px;
    padding: 3px 11px;
    font: inherit;
    font-size: 11.5px;
    color: var(--eden-app-muted);
    cursor: pointer;
  }
  .tg.on {
    background: color-mix(in oklab, var(--eden-app-accent) 12%, var(--eden-app-panel-bg));
    border-color: var(--eden-app-accent);
    color: var(--eden-app-accent);
  }
  .flow {
    position: relative;
    flex: 1;
    min-height: 0;
    background: var(--eden-app-bg);
  }
  :global(.flow .svelte-flow) {
    background: var(--eden-app-bg);
  }
</style>
