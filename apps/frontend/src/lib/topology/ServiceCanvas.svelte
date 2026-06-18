<script lang="ts">
  import { SvelteFlow, Background, Controls, MiniMap } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import ServiceNode from './ServiceNode.svelte';
  import NsGroup from './NsGroup.svelte';
  import KindIcon from './KindIcon.svelte';
  import { buildFlow } from './layout';
  import type { Topology, TopoNode } from './contract';

  let { topology }: { topology: Topology } = $props();
  let view = $state('architecture');
  let selected = $state<TopoNode | null>(null);

  let nodes = $state.raw<any[]>([]);
  let edges = $state.raw<any[]>([]);
  $effect(() => {
    const f = buildFlow(topology, view);
    nodes = f.nodes;
    edges = f.edges;
    selected = null;
  });

  const nodeTypes = { service: ServiceNode, nsgroup: NsGroup } as any;

  function onNodeClick(e: any) {
    const node = e?.node ?? e?.detail?.node;
    if (node?.data?.node) selected = node.data.node as TopoNode;
  }
  const ago = $derived(new Date(topology.generatedAt).toLocaleString());
</script>

<div class="wrap">
  <div class="bar">
    <div class="tabs">
      {#each topology.views as v}
        <button class:active={view === v.id} onclick={() => (view = v.id)} title={v.description}>{v.title}</button>
      {/each}
    </div>
    <div class="meta">live snapshot · {ago}</div>
  </div>

  <div class="flow">
    <SvelteFlow
      bind:nodes
      bind:edges
      {nodeTypes}
      colorMode="dark"
      fitView
      minZoom={0.15}
      nodesDraggable={false}
      nodesConnectable={false}
      onnodeclick={onNodeClick}
    >
      <Background gap={20} />
      <Controls showLock={false} />
      <MiniMap pannable zoomable nodeColor="#2b2f44" maskColor="rgba(13,15,22,.6)" />
    </SvelteFlow>

    {#if selected}
      <aside class="detail">
        <button class="x" onclick={() => (selected = null)} aria-label="close">✕</button>
        <div class="dh"><span class="di"><KindIcon kind={selected.kind} size={22} /></span>
          <div><div class="dn">{selected.name}</div><div class="dk">{selected.kind}{selected.namespace ? ` · ${selected.namespace}` : ''}</div></div>
        </div>
        {#if selected.status}<div class="st st-{selected.status}">{selected.status}</div>{/if}
        <dl>
          {#each Object.entries(selected.meta) as [k, v]}
            {#if v}<dt>{k}</dt><dd>{v}</dd>{/if}
          {/each}
        </dl>
        <button class="k9s" title="Opens a live k9s session for this resource (ttyd) — coming next">⎈ Open in k9s</button>
      </aside>
    {/if}
  </div>
</div>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .bar { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid #1d2030; background: #0e1018; }
  .tabs { display: flex; gap: 4px; }
  .tabs button { background: transparent; color: #7a82a8; border: 1px solid transparent; border-radius: 7px; padding: 6px 12px; font: 600 12px/1 ui-sans-serif, system-ui; cursor: pointer; }
  .tabs button:hover { color: #c0caf5; }
  .tabs button.active { color: #c0caf5; background: #1b1e2b; border-color: #2b2f44; }
  .meta { color: #565f89; font: 11px ui-sans-serif, system-ui; }
  .flow { position: relative; flex: 1; min-height: 0; background: #0d0f16; }
  :global(.flow .svelte-flow) { background: #0d0f16; }
  .detail { position: absolute; top: 12px; right: 12px; width: 280px; max-height: calc(100% - 24px); overflow: auto; background: #12141d; border: 1px solid #2b2f44; border-radius: 12px; padding: 14px; color: #c0caf5; box-shadow: 0 8px 30px rgba(0,0,0,.45); font: 12px/1.4 ui-sans-serif, system-ui; }
  .x { position: absolute; top: 8px; right: 10px; background: none; border: none; color: #565f89; cursor: pointer; font-size: 13px; }
  .dh { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
  .di { color: #7aa2f7; }
  .dn { font-weight: 700; font-size: 14px; }
  .dk { color: #7a82a8; font-size: 11px; }
  .st { display: inline-block; border-radius: 999px; padding: 2px 9px; font-size: 11px; font-weight: 600; margin-bottom: 10px; }
  .st-ok { background: rgba(158,206,106,.15); color: #9ece6a; }
  .st-warn { background: rgba(224,175,104,.15); color: #e0af68; }
  .st-down { background: rgba(247,118,142,.15); color: #f7768e; }
  .st-unknown { background: #1b1e2b; color: #565f89; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; margin: 0 0 12px; }
  dt { color: #7a82a8; }
  dd { margin: 0; text-align: right; word-break: break-all; }
  .k9s { width: 100%; background: #1b1e2b; color: #7aa2f7; border: 1px solid #2b2f44; border-radius: 8px; padding: 9px; font: 600 12px ui-sans-serif, system-ui; cursor: pointer; }
  .k9s:hover { background: #21263a; }
</style>
