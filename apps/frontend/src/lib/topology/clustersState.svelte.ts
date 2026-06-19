// The ONE shared state every Atlas lens reads (linked views): which cluster, which lens, the
// namespace/status/text filters, the focused node (drawer), and the Service-Map edge toggles.
// A single rune store rather than threaded props keeps selection coherent across the Scorecard,
// Overview, Endpoints, Inventory, Service Map and the shared Detail drawer, and lets the page mirror
// it to the URL so an on-call engineer can paste "the broken view".
import type { EdgeKind, Status, TopoNode } from './contract';

export type Lens = 'overview' | 'endpoints' | 'map' | 'inventory';
export const LENSES: { id: Lens; title: string }[] = [
  { id: 'overview', title: 'Overview' },
  { id: 'endpoints', title: 'Endpoints' },
  { id: 'map', title: 'Service Map' },
  { id: 'inventory', title: 'Inventory' },
];

export class ClustersState {
  clusterId = $state('');
  lens = $state<Lens>('overview');
  /** Namespace scope (empty = all namespaces). */
  namespaces = $state<Set<string>>(new Set());
  /** Status facet (empty = all statuses). */
  statuses = $state<Set<Status>>(new Set());
  /** Free-text faceted search (name / namespace / image / host). */
  query = $state('');
  /** The focused node id → the shared Detail drawer (null = closed). */
  focusId = $state<string | null>(null);
  /** Service-Map edge kinds drawn (routes + depends are meaningful by default). */
  mapEdges = $state<Set<EdgeKind>>(new Set<EdgeKind>(['routes', 'depends']));

  setCluster(id: string): void {
    if (id === this.clusterId) return;
    this.clusterId = id;
    this.namespaces = new Set();
    this.statuses = new Set();
    this.query = '';
    this.focusId = null;
  }

  setLens(l: Lens): void {
    this.lens = l;
  }

  toggleStatus(s: Status): void {
    const next = new Set(this.statuses);
    next.has(s) ? next.delete(s) : next.add(s);
    this.statuses = next;
  }

  toggleNamespace(name: string): void {
    const next = new Set(this.namespaces);
    next.has(name) ? next.delete(name) : next.add(name);
    this.namespaces = next;
  }

  toggleEdge(kind: EdgeKind): void {
    const next = new Set(this.mapEdges);
    next.has(kind) ? next.delete(kind) : next.add(kind);
    this.mapEdges = next;
  }

  /** Scope to one namespace and jump to the Service Map (drill-in from a card). */
  scopeToMap(name: string): void {
    this.namespaces = new Set([name]);
    this.lens = 'map';
  }

  /** Filter to a single status across the active lens (a Scorecard count chip). */
  filterStatus(s: Status): void {
    this.statuses = new Set([s]);
  }

  focus(id: string | null): void {
    this.focusId = id;
  }

  clearFilters(): void {
    this.namespaces = new Set();
    this.statuses = new Set();
    this.query = '';
  }

  get hasFilters(): boolean {
    return this.namespaces.size > 0 || this.statuses.size > 0 || this.query.trim().length > 0;
  }

  /** Does a node pass the active namespace/status/text filters? (Used by every lens.) */
  matches(n: TopoNode): boolean {
    if (this.namespaces.size && !(n.namespace && this.namespaces.has(n.namespace))) return false;
    if (this.statuses.size && !this.statuses.has(n.status ?? 'unknown')) return false;
    const q = this.query.trim().toLowerCase();
    if (q) {
      const hay = `${n.name} ${n.namespace ?? ''} ${n.kind} ${n.meta.image ?? ''} ${n.meta.hosts ?? ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  /** Serialize to URL params (only non-default keys) so a view is shareable. */
  toQuery(): URLSearchParams {
    const p = new URLSearchParams();
    if (this.clusterId) p.set('cluster', this.clusterId);
    if (this.lens !== 'overview') p.set('lens', this.lens);
    if (this.namespaces.size) p.set('ns', [...this.namespaces].join(','));
    if (this.statuses.size) p.set('status', [...this.statuses].join(','));
    if (this.query.trim()) p.set('q', this.query.trim());
    if (this.focusId) p.set('focus', this.focusId);
    return p;
  }

  /** Hydrate from URL params (deep-link / reload). */
  applyQuery(p: URLSearchParams, fallbackCluster: string): void {
    this.clusterId = p.get('cluster') || fallbackCluster;
    const lens = p.get('lens') as Lens | null;
    if (lens && LENSES.some((l) => l.id === lens)) this.lens = lens;
    this.namespaces = new Set((p.get('ns') ?? '').split(',').filter(Boolean));
    this.statuses = new Set(
      (p.get('status') ?? '').split(',').filter(Boolean) as Status[],
    );
    this.query = p.get('q') ?? '';
    this.focusId = p.get('focus');
  }
}

/** The shared instance the page + every lens read. */
export const clusters = new ClustersState();
