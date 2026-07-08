// Deterministic namespace-grouped layout: each namespace becomes a box (group node), its members
// laid out in a sub-grid, and the boxes flow left-to-right wrapping to the next shelf. No external
// layout engine — readable + stable for ~60 nodes. Returns Svelte Flow nodes/edges. Edge styling is
// token-driven (Eden light theme); the caller chooses which edge kinds are drawn (routes+depends are
// meaningful by default; selects/mounts are opt-in) and an optional namespace scope (scope-first).
import type { EdgeKind, Topology, TopoNode } from './contract';

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

export interface BuildOptions {
  /** Which edge kinds to draw (`contains` is never drawn). */
  edgeKinds: Set<EdgeKind>;
  /** Namespace names to include; empty/undefined = the whole cluster. */
  scope?: Set<string>;
  /** The focused node id → 1-hop neighbourhood stays solid, the rest dims (focus+context). */
  focusId?: string | null;
}

const CELL_W = 190,
  CELL_H = 74,
  GAP = 14,
  HEADER = 34,
  PAD = 14;
const SHELF_W = 1680,
  NS_GAP = 28;

// Edge styling reads ONLY generated tokens — meaning, not decoration.
const EDGE_STYLE: Record<EdgeKind, string> = {
  routes: 'stroke:var(--color-primary);stroke-width:1.8',
  depends: 'stroke:color-mix(in oklab, var(--color-on-surface) 45%, transparent);stroke-width:1.3',
  selects: 'stroke:var(--color-outline);stroke-width:1.1;stroke-dasharray:5 4',
  mounts: 'stroke:var(--color-warning);stroke-width:1.2;stroke-dasharray:2 3',
  contains: '',
};

export function buildFlow(
  topo: Topology,
  opts: BuildOptions,
): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const scope = opts.scope && opts.scope.size ? opts.scope : null;
  const keepMember = (n: TopoNode) =>
    n.kind !== 'namespace' && (!scope || (n.namespace != null && scope.has(n.namespace)));

  const members = topo.nodes.filter(keepMember);
  const keptIds = new Set(members.map((m) => m.id));

  const linkEdges = topo.edges
    .filter((e) => e.kind !== 'contains' && opts.edgeKinds.has(e.kind))
    .filter((e) => keptIds.has(e.source) && keptIds.has(e.target));

  // focus+context neighbourhood (ids 1 hop from the focused node along the drawn edges).
  const neighbours = new Set<string>();
  if (opts.focusId && keptIds.has(opts.focusId)) {
    neighbours.add(opts.focusId);
    for (const e of linkEdges) {
      if (e.source === opts.focusId) neighbours.add(e.target);
      if (e.target === opts.focusId) neighbours.add(e.source);
    }
  }
  const dim = (id: string) => neighbours.size > 0 && !neighbours.has(id);

  const byNs = new Map<string, TopoNode[]>();
  for (const m of members) {
    const ns = m.namespace ?? '—';
    const list = byNs.get(ns) ?? [];
    list.push(m);
    byNs.set(ns, list);
  }
  // biggest namespace first for a tidy pack
  const namespaces = [...byNs.entries()].sort((a, b) => b[1].length - a[1].length);

  const nodes: FlowNode[] = [];
  let shelfX = 0,
    shelfY = 0,
    shelfMaxH = 0;

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
      id: gid,
      type: 'nsgroup',
      position: { x: shelfX, y: shelfY },
      data: { name: ns, count: mem.length },
      width: w,
      height: h,
      draggable: false,
      selectable: false,
      style: `width:${w}px;height:${h}px;`,
    });
    mem.forEach((m, i) => {
      const c = i % cols,
        r = Math.floor(i / cols);
      nodes.push({
        id: m.id,
        type: 'service',
        parentId: gid,
        extent: 'parent',
        position: { x: PAD + c * (CELL_W + GAP), y: HEADER + PAD + r * (CELL_H + GAP) },
        data: { node: m, dimmed: dim(m.id) },
        draggable: false,
        width: CELL_W,
        height: CELL_H,
      });
    });
    shelfX += w + NS_GAP;
    shelfMaxH = Math.max(shelfMaxH, h);
  }

  return {
    nodes,
    edges: linkEdges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: 'bezier',
      animated: false,
      data: { kind: e.kind },
      style: `${EDGE_STYLE[e.kind] || EDGE_STYLE.selects}${dim(e.source) || dim(e.target) ? ';opacity:.12' : ''}`,
    })),
  };
}
