// The document model the UI reasons over: tier derivation (doc 11 §2), status
// vocabulary (doc 11 §4), and the small derived helpers the workspace shares
// between server load functions and components. Pure data + functions, no I/O —
// safe to import from anywhere.

// The three authored tiers (doc 11 §2: Product → Architecture → Implementation),
// each with the meta.type values that belong to it. The list mirrors
// docs/tools/render-documents.mjs so the Svelte app and the static render group
// documents identically (one concept, one home). meta.type for an ADR is the
// singular `architecture-decision` (the validator's projection type), distinct
// from the document-id grammar's `adr-NNNN`.
export interface Tier {
  readonly key: 'product' | 'architecture' | 'implementation';
  readonly label: string;
  readonly types: readonly string[];
}

export const TIERS: readonly Tier[] = [
  {
    key: 'product',
    label: 'Product',
    types: ['product-charter', 'requirements', 'user-workflows', 'design-brief'],
  },
  {
    key: 'architecture',
    label: 'Architecture',
    types: ['domain-model', 'system-design', 'service-contracts', 'architecture-decision'],
  },
  {
    key: 'implementation',
    label: 'Implementation',
    types: ['implementation-plan', 'specification'],
  },
];

// The tier a document type belongs to. An unknown type sorts into implementation
// (the most-downstream tier) rather than throwing — a new schema type should still
// render, just at the bottom, until the registry above learns it.
export function tierOf(type: string): Tier['key'] {
  return TIERS.find((tier) => tier.types.includes(type))?.key ?? 'implementation';
}

// A document type's position within its tier, for stable in-tier ordering
// (matches the render-documents.mjs typeRank so the two surfaces agree).
export function typeRank(type: string): number {
  const tier = TIERS.find((entry) => entry.types.includes(type));
  if (!tier) return 99;
  const index = tier.types.indexOf(type);
  return index < 0 ? 99 : index;
}

// The status lifecycle (doc 11 §4: draft → review → approved → superseded) and
// its display ordering. Each status maps to a chip tone (the --chip-* tokens in
// +layout.svelte), aligned to the render-documents.mjs status palette: draft warns
// (amber), review informs (the in-progress state reads as info), approved is ok
// (green), superseded is muted.
export const STATUS_ORDER = ['draft', 'review', 'approved', 'superseded'] as const;
export type DocumentStatus = (typeof STATUS_ORDER)[number];

export type ChipTone = 'neutral' | 'info' | 'ok' | 'warn' | 'muted';

export function statusTone(status: string): ChipTone {
  switch (status) {
    case 'approved':
      return 'ok';
    case 'review':
      return 'info';
    case 'draft':
      return 'warn';
    case 'superseded':
      return 'muted';
    default:
      return 'neutral';
  }
}

// A human title for a document from its meta. Registry documents (yaml) carry a
// type-only identity; narrative documents (md) may carry a richer id. The title is
// the id with separators humanized, which reads cleanly for both
// (`product-charter` → `Product charter`, `adr-0001` → `Adr 0001`).
export function documentTitle(meta: { id: string; type: string }): string {
  const base = meta.id || meta.type;
  const spaced = base.replace(/[-_]/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

// The item-id grammar (doc 11 §3): PREFIX-NNNN. A string is an item id when it
// matches; this drives in-document anchors and link-chip navigability. The known
// prefixes are listed so an arbitrary uppercase token is not mistaken for one.
const ITEM_ID = /^(PER|REQ|WF|ENT|INV|CMP|CTR|ADR|WP|SPEC)-\d{4}$/;

export function isItemId(value: string): boolean {
  return ITEM_ID.test(value);
}
