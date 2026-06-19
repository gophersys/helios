<script lang="ts">
  // A Service-Map node — STATUS owns colour (the left rail + glyph), KIND owns the icon (resolves the
  // old bug where green meant both 'deployment' and 'ok'). Token-driven (Eden light theme); dims to
  // context when another node is focused.
  import { Handle, Position } from '@xyflow/svelte';
  import KindIcon from './KindIcon.svelte';
  import StatusGlyph from './StatusGlyph.svelte';
  import { statusColor } from './status';
  import { classOf } from './model';
  import type { TopoNode } from './contract';

  let { data }: { data: { node: TopoNode; dimmed?: boolean } } = $props();
  const n = $derived(data.node);
  const sub = $derived(
    n.meta.replicas ? `${n.meta.kind ?? classOf(n)} · ${n.meta.replicas}` :
    n.meta.type ? `${n.meta.kind ?? classOf(n)} · ${n.meta.type}` :
    n.meta.hosts ? n.meta.hosts :
    n.meta.capacity ? `${n.meta.kind ?? classOf(n)} · ${n.meta.capacity}` : (n.meta.kind ?? classOf(n)),
  );
</script>

<div class="svc" class:dimmed={data.dimmed} style="--rail:{statusColor(n.status)}">
  <Handle type="target" position={Position.Left} style="opacity:0" />
  <span class="ic"><KindIcon kind={n.kind} /></span>
  <span class="txt">
    <span class="name" title={n.name}>{n.name}</span>
    <span class="sub" title={n.meta.image ?? ''}>{sub}</span>
  </span>
  <span class="st"><StatusGlyph status={n.status ?? 'unknown'} size={11} /></span>
  <Handle type="source" position={Position.Right} style="opacity:0" />
</div>

<style>
  .svc {
    display: flex;
    align-items: center;
    gap: 9px;
    width: 190px;
    height: 74px;
    box-sizing: border-box;
    padding: 10px 12px;
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-left: 3px solid var(--rail);
    border-radius: 9px;
    color: var(--eden-app-fg);
    box-shadow: 0 1px 2px color-mix(in oklab, var(--eden-app-fg) 8%, transparent);
    font: 12px/1.3 var(--font-text);
    position: relative;
    transition: opacity 140ms ease;
  }
  .dimmed {
    opacity: 0.22;
  }
  .ic {
    color: var(--eden-app-muted);
    display: grid;
    place-items: center;
    flex: none;
  }
  .txt {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }
  .name {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .sub {
    color: var(--eden-app-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 11px;
    font-family: var(--font-code);
  }
  .st {
    position: absolute;
    top: 8px;
    right: 9px;
  }
</style>
