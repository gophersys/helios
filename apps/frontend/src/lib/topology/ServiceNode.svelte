<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte';
  import KindIcon from './KindIcon.svelte';
  import type { TopoNode } from './contract';

  let { data }: { data: { node: TopoNode } } = $props();
  const n = $derived(data.node);
  const accent: Record<string, string> = {
    ingress: '#7aa2f7', service: '#7dcfff', deployment: '#9ece6a', statefulset: '#9ece6a',
    daemonset: '#9ece6a', database: '#e0af68', cache: '#f7768e', queue: '#bb9af7',
    pvc: '#c9a227', secretstore: '#ff9e64', cronjob: '#73daca', external: '#a9b1d6',
  };
  const statusColor: Record<string, string> = { ok: '#9ece6a', warn: '#e0af68', down: '#f7768e', unknown: '#565f89' };
  const sub = $derived(
    n.meta.replicas ? `${n.kind} · ${n.meta.replicas}` :
    n.meta.type ? `${n.kind} · ${n.meta.type}` :
    n.meta.hosts ? n.meta.hosts :
    n.meta.capacity ? `${n.kind} · ${n.meta.capacity}` : n.kind
  );
</script>

<div class="svc" style="--accent:{accent[n.kind] ?? '#a9b1d6'}">
  <Handle type="target" position={Position.Left} style="opacity:0" />
  <span class="dot" style="background:{statusColor[n.status ?? 'unknown']}"></span>
  <span class="ic"><KindIcon kind={n.kind} /></span>
  <span class="txt">
    <span class="name" title={n.name}>{n.name}</span>
    <span class="sub" title={n.meta.image ?? ''}>{sub}</span>
  </span>
  <Handle type="source" position={Position.Right} style="opacity:0" />
</div>

<style>
  .svc {
    display: flex; align-items: center; gap: 9px;
    width: 188px; height: 76px; box-sizing: border-box; padding: 10px 12px;
    background: #1b1e2b; border: 1px solid #2b2f44; border-left: 3px solid var(--accent);
    border-radius: 9px; color: #c0caf5; box-shadow: 0 1px 3px rgba(0,0,0,.35);
    font: 12px/1.3 ui-sans-serif, system-ui, sans-serif; position: relative;
  }
  .dot { position: absolute; top: 8px; right: 9px; width: 7px; height: 7px; border-radius: 50%; }
  .ic { color: var(--accent); display: grid; place-items: center; flex: none; }
  .txt { display: flex; flex-direction: column; min-width: 0; }
  .name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub { color: #7a82a8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px; }
</style>
