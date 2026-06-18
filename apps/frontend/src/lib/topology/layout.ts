// Deterministic namespace-grouped layout: each namespace becomes a box (group node), its members
// laid out in a sub-grid, and the boxes flow left-to-right wrapping to the next shelf. No external
// layout engine — readable + stable for ~60 nodes. Returns Svelte Flow nodes/edges for a given view.
import type { Topology, TopoNode, EdgeKind } from './contract';

export interface FlowNode {
  id: string;
  type: 'service' | 'nsgroup';
  position: { x: number; y: number };
  data: Record<string, unknown>;
  parentId?: string;
  extent?: 'parent';
  draggable?: boolean;
  selectable?: boolean;
  width?: number;
  height?: number;
  style?: string;
}
export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  animated?: boolean;
  data?: { kind: EdgeKind };
  style?: string;
}

const CELL_W = 188, CELL_H = 76, GAP = 14, HEADER = 34, PAD = 14;
const SHELF_W = 1680, NS_GAP = 28;

const FLOW_KINDS = new Set(['ingress', 'service', 'deployment', 'statefulset', 'daemonset', 'database', 'cache', 'queue', 'pvc']);

export function buildFlow(topo: Topology, viewId: string): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const dataflow = viewId === 'dataflow';
  const keepMember = (n: TopoNode) => n.kind !== 'namespace' && (!dataflow || FLOW_KINDS.has(n.kind));

  const members = topo.nodes.filter(keepMember);
  const keptIds = new Set(members.map((m) => m.id));
  const byNs = new Map<string, TopoNode[]>();
  for (const m of members) {
    const ns = m.namespace ?? '—';
    (byNs.get(ns) ?? byNs.set(ns, []).get(ns)!).push(m);
  }

  // order namespaces by size (biggest first) for a tidy pack
  const namespaces = [...byNs.entries()].sort((a, b) => b[1].length - a[1].length);

  const nodes: FlowNode[] = [];
  let shelfX = 0, shelfY = 0, shelfMaxH = 0;

  for (const [ns, mem] of namespaces) {
    const cols = Math.min(4, Math.ceil(Math.sqrt(mem.length)));
    const rows = Math.ceil(mem.length / cols);
    const w = PAD * 2 + cols * CELL_W + (cols - 1) * GAP;
    const h = HEADER + PAD + rows * CELL_H + (rows - 1) * GAP + PAD;

    if (shelfX > 0 && shelfX + w > SHELF_W) {
      shelfX = 0;
      shelfY += shelfMaxH + NS_GAP;
      shelfMaxH = 0;
    }
    const gid = `ns/${ns}`;
    nodes.push({
      id: gid, type: 'nsgroup', position: { x: shelfX, y: shelfY },
      data: { name: ns, count: mem.length }, width: w, height: h,
      draggable: false, selectable: false, style: `width:${w}px;height:${h}px;`,
    });
    mem.forEach((m, i) => {
      const c = i % cols, r = Math.floor(i / cols);
      nodes.push({
        id: m.id, type: 'service', parentId: gid, extent: 'parent',
        position: { x: PAD + c * (CELL_W + GAP), y: HEADER + PAD + r * (CELL_H + GAP) },
        data: { node: m }, draggable: false, width: CELL_W, height: CELL_H,
      });
    });
    shelfX += w + NS_GAP;
    shelfMaxH = Math.max(shelfMaxH, h);
  }

  const edgeStyle: Record<string, string> = {
    routes: 'stroke:var(--eden-accent, #7aa2f7);stroke-width:1.6',
    selects: 'stroke:var(--eden-border-strong, #8a8f98);stroke-width:1.2',
    mounts: 'stroke:#c9a227;stroke-width:1.2;stroke-dasharray:4 3',
    depends: 'stroke:#9d7cd8;stroke-width:1.2;stroke-dasharray:2 3',
  };
  const edges: FlowEdge[] = topo.edges
    .filter((e) => e.kind !== 'contains' && keptIds.has(e.source) && keptIds.has(e.target))
    .filter((e) => (dataflow ? e.kind === 'routes' || e.kind === 'selects' || e.kind === 'mounts' : true))
    .map((e) => ({
      id: e.id, source: e.source, target: e.target, type: 'bezier',
      animated: dataflow && (e.kind === 'routes' || e.kind === 'selects'),
      data: { kind: e.kind }, style: edgeStyle[e.kind] ?? edgeStyle.selects,
    }));

  return { nodes, edges };
}
