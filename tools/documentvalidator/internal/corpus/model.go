// Package corpus builds the cross-document link graph for a project and enforces
// the traceability rules T1-T5 from doc 11 §7, plus the T6 coverage report.
//
// The corpus is the set of all project documents under a target directory.
// Shape (JSON Schema) has already been checked per document by the caller; the
// rules here are the cross-document invariants no single schema can express:
// that every linked id resolves (T1), points upstream (T2), grounds architecture
// in product (T3) and implementation in contracts (T4), that no id is defined
// twice (T5), and which P1 requirements still lack a specification path (T6).
package corpus

import (
	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// Tier is the coarse document tier (doc 11 §2): product, architecture, or
// implementation. Direction (T2) is enforced on a finer per-document rank, but
// the coarse tier names the bands T3/T4 reason about.
type Tier int

const (
	// TierProduct is the P tier: what/why (charter, requirements, workflows,
	// design-brief).
	TierProduct Tier = iota
	// TierArchitecture is the A tier: how (domain-model, system-design,
	// service-contracts, architecture-decision).
	TierArchitecture
	// TierImplementation is the I tier: build-against (implementation-plan,
	// specification).
	TierImplementation
)

func (t Tier) String() string {
	switch t {
	case TierProduct:
		return "product"
	case TierArchitecture:
		return "architecture"
	case TierImplementation:
		return "implementation"
	default:
		return "unknown"
	}
}

// itemKind describes the document type an item prefix lives in, carrying both
// the fine rank used for direction (T2) and the coarse tier used for T3/T4. The
// fine rank follows the document enumeration order of doc 11 §6 / the validator
// spec's tier list, so that within-tier citations (e.g. an ADR realizing a
// component, or a contract realizing a component) are correctly upstream.
type itemKind struct {
	rank int
	tier Tier
}

// prefixKind maps an item-id prefix (doc 11 §3) to its document rank and tier.
// SPEC items do not appear as item ids in document bodies (a specification is a
// whole document, cited via its data fields), but the prefix is included for
// completeness of the grammar.
var prefixKind = map[string]itemKind{
	"PER":  {rank: 0, tier: TierProduct},        // product-charter
	"REQ":  {rank: 1, tier: TierProduct},        // requirements
	"WF":   {rank: 2, tier: TierProduct},        // user-workflows
	"ENT":  {rank: 4, tier: TierArchitecture},   // domain-model
	"INV":  {rank: 4, tier: TierArchitecture},   // domain-model
	"CMP":  {rank: 5, tier: TierArchitecture},   // system-design
	"CTR":  {rank: 6, tier: TierArchitecture},   // service-contracts
	"ADR":  {rank: 7, tier: TierArchitecture},   // architecture-decision
	"WP":   {rank: 8, tier: TierImplementation}, // implementation-plan
	"SPEC": {rank: 9, tier: TierImplementation}, // specification
}

// Item is a single identified element in the corpus (an item id such as
// REQ-0007, or a document id such as adr-0001 / spec-0001 that participates in
// the link graph).
type Item struct {
	// ID is the item or document identifier.
	ID string
	// Prefix is the uppercase item-id prefix (e.g. REQ); empty for document ids.
	Prefix string
	// DefinedIn is the path of the document that defines this item.
	DefinedIn string
	// Rank is the fine direction rank; tier is the coarse tier. Only meaningful
	// for prefixed item ids.
	Rank int
	Tier Tier
	// IsDocument is true for document ids (adr-NNNN, spec-NNNN, requirements,
	// …) registered to resolve link targets, false for body item ids.
	IsDocument bool
	// Priority is the requirement priority (P1/P2/P3) for REQ items; empty
	// otherwise. Used by the T6 coverage report.
	Priority string
}

// Edge is one typed link between a source item/document and a target reference
// (doc 11 §3 link types). Reverse edges are never authored; they are derived by
// querying this list.
type Edge struct {
	// From is the id of the item or document that authored the link.
	From string
	// FromPath is the document the edge was authored in (for diagnostics).
	FromPath string
	// Type is the link type: realizes, refines, verifies, informs, supersedes.
	Type string
	// To is the raw reference string the link points at.
	To string
}

// Diagnostic is a single rule violation or report line, emitted in a stable
// order with enough context to locate and explain it.
type Diagnostic struct {
	// File is the source document the diagnostic concerns.
	File string
	// DocumentID is the document or item id at fault (may be empty).
	DocumentID string
	// Rule is the rule code (T1-T6) or a sentinel for non-rule reports.
	Rule string
	// Message is the human-readable explanation.
	Message string
}

// SpecCite captures a specification's two mandatory citations (T4): the single
// work package and single contract it is written against. Read from the
// projected spec document's data block, not from its link edges.
type SpecCite struct {
	DocID       string
	Path        string
	WorkPackage string
	Contract    string
}

// Corpus is the assembled project: every defined item/document, the full edge
// list, and the per-document specification citations.
type Corpus struct {
	// Items is keyed by id. On a duplicate id the first definition wins and the
	// duplicate is recorded in Duplicates (T5).
	Items map[string]*Item
	// Edges is the full link-edge list, in document then declaration order.
	Edges []Edge
	// Specs is the list of specification citations, in path order.
	Specs []SpecCite
	// Duplicates holds (id, path) pairs for every redefinition past the first.
	Duplicates []duplicate
	// docTypeRank maps a document type slug to its rank, used to rank
	// document-id link targets (e.g. supersedes, realizes -> a document).
	docTypeRank map[string]int
}

type duplicate struct {
	id   string
	path string
}

// documentTypeRank gives the fine direction rank of each document type, mirroring
// prefixKind so that links to document ids (rather than item ids) rank correctly.
var documentTypeRank = map[string]struct {
	rank int
	tier Tier
}{
	"product-charter":       {0, TierProduct},
	"requirements":          {1, TierProduct},
	"user-workflows":        {2, TierProduct},
	"design-brief":          {3, TierProduct},
	"domain-model":          {4, TierArchitecture},
	"system-design":         {5, TierArchitecture},
	"service-contracts":     {6, TierArchitecture},
	"architecture-decision": {7, TierArchitecture},
	"implementation-plan":   {8, TierImplementation},
	"specification":         {9, TierImplementation},
}

// Build assembles a Corpus from already-projected documents, recording every
// item, edge, and spec citation. It does not run the rules; call the Check*
// methods (or CheckAll) for that.
func Build(docs []*projection.Document) *Corpus {
	c := &Corpus{
		Items:       map[string]*Item{},
		docTypeRank: map[string]int{},
	}
	for ty, info := range documentTypeRank {
		c.docTypeRank[ty] = info.rank
	}
	for _, d := range docs {
		c.ingest(d)
	}
	return c
}
