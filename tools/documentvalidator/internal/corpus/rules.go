package corpus

import (
	"fmt"
	"sort"
	"strings"
)

// isExternalReference reports whether a reference is an external artifact or
// path reference (artifact:// or path://), which the corpus rules skip — those
// targets live outside the project document graph (doc 11 §3, validator spec).
func isExternalReference(ref string) bool {
	return strings.HasPrefix(ref, "artifact://") || strings.HasPrefix(ref, "path://")
}

// CheckAll runs the error rules (T1-T5) and returns their diagnostics in stable
// order. T6 is a separate report (see CoverageReport), not an error.
func (c *Corpus) CheckAll() []Diagnostic {
	var diags []Diagnostic
	diags = append(diags, c.checkDuplicates()...) // T5
	diags = append(diags, c.checkResolution()...) // T1
	diags = append(diags, c.checkDirection()...)  // T2
	diags = append(diags, c.checkArchToProd()...) // T3
	diags = append(diags, c.checkImplCites()...)  // T4
	return sortDiagnostics(diags)
}

// checkDuplicates emits T5: a duplicate id is an error. Reported once per
// redefinition past the first.
func (c *Corpus) checkDuplicates() []Diagnostic {
	var diags []Diagnostic
	for _, d := range c.Duplicates {
		first := c.Items[d.id]
		firstPath := ""
		if first != nil {
			firstPath = first.DefinedIn
		}
		diags = append(diags, Diagnostic{
			File:       d.path,
			DocumentID: d.id,
			Rule:       "T5",
			Message:    fmt.Sprintf("duplicate id %q (first defined in %s)", d.id, firstPath),
		})
	}
	return diags
}

// checkResolution emits T1: every link target must resolve within the corpus.
// External artifact:// and path:// references are skipped.
func (c *Corpus) checkResolution() []Diagnostic {
	var diags []Diagnostic
	for _, e := range c.Edges {
		if e.To == "" || isExternalReference(e.To) {
			continue
		}
		if _, ok := c.Items[e.To]; !ok {
			diags = append(diags, Diagnostic{
				File:       e.FromPath,
				DocumentID: e.From,
				Rule:       "T1",
				Message:    fmt.Sprintf("%s link target %q does not resolve in the project corpus", e.Type, e.To),
			})
		}
	}
	// A specification's work_package / contract citations must also resolve.
	for _, s := range c.Specs {
		if s.WorkPackage != "" {
			if _, ok := c.Items[s.WorkPackage]; !ok {
				diags = append(diags, Diagnostic{
					File:       s.Path,
					DocumentID: s.DocID,
					Rule:       "T1",
					Message:    fmt.Sprintf("work_package %q does not resolve in the project corpus", s.WorkPackage),
				})
			}
		}
		if s.Contract != "" {
			if _, ok := c.Items[s.Contract]; !ok {
				diags = append(diags, Diagnostic{
					File:       s.Path,
					DocumentID: s.DocID,
					Rule:       "T1",
					Message:    fmt.Sprintf("contract %q does not resolve in the project corpus", s.Contract),
				})
			}
		}
	}
	return diags
}

// checkDirection emits T2: links point upstream only. A link is upstream when
// the target's rank is strictly less than the source's (a document closer to
// product). Same-rank links are allowed only for `refines` (same-tier
// elaboration, doc 11 §3). `supersedes` is exempt (a new version pointing at the
// document it replaces, same type by construction). External references are
// skipped; unresolved targets are left to T1.
func (c *Corpus) checkDirection() []Diagnostic {
	var diags []Diagnostic
	for _, e := range c.Edges {
		if e.Type == "supersedes" || e.To == "" || isExternalReference(e.To) {
			continue
		}
		from, okFrom := c.Items[e.From]
		to, okTo := c.Items[e.To]
		if !okFrom || !okTo {
			continue // resolution is T1's concern; ranking needs both ends.
		}
		switch {
		case to.Rank < from.Rank:
			// strictly upstream — fine.
		case to.Rank == from.Rank:
			if e.Type != "refines" {
				diags = append(diags, Diagnostic{
					File:       e.FromPath,
					DocumentID: e.From,
					Rule:       "T2",
					Message:    fmt.Sprintf("%s link to same-tier id %q is not upstream (only `refines` may link within a tier)", e.Type, e.To),
				})
			}
		default: // to.Rank > from.Rank
			diags = append(diags, Diagnostic{
				File:       e.FromPath,
				DocumentID: e.From,
				Rule:       "T2",
				Message:    fmt.Sprintf("%s link to %q points downstream (links must point upstream only)", e.Type, e.To),
			})
		}
	}
	return diags
}

// checkArchToProd emits T3: every architecture-tier item must carry at least one
// `realizes` edge that reaches the product tier through the realizes graph. An
// architecture item with no realizes edge, or whose realizes chain never reaches
// a product item, is unmotivated architecture.
func (c *Corpus) checkArchToProd() []Diagnostic {
	realizes := c.realizesAdjacency()
	var diags []Diagnostic
	ids := sortedItemIDs(c.Items)
	for _, id := range ids {
		item := c.Items[id]
		if item.IsDocument || item.Tier != TierArchitecture {
			continue
		}
		if !reachesProduct(id, realizes, c.Items) {
			diags = append(diags, Diagnostic{
				File:       item.DefinedIn,
				DocumentID: id,
				Rule:       "T3",
				Message:    "architecture-tier item carries no `realizes` edge reaching the product tier",
			})
		}
	}
	return diags
}

// checkImplCites emits T4: every work package must realize at least one contract
// or requirement; every specification must cite exactly one work package and
// exactly one contract.
func (c *Corpus) checkImplCites() []Diagnostic {
	var diags []Diagnostic

	// Index realizes targets per WP.
	wpRealizes := map[string][]string{}
	for _, e := range c.Edges {
		if e.Type == "realizes" && prefixOf(e.From) == "WP" {
			wpRealizes[e.From] = append(wpRealizes[e.From], e.To)
		}
	}
	for _, id := range sortedItemIDs(c.Items) {
		item := c.Items[id]
		if item.Prefix != "WP" {
			continue
		}
		if !realizesContractOrReq(wpRealizes[id]) {
			diags = append(diags, Diagnostic{
				File:       item.DefinedIn,
				DocumentID: id,
				Rule:       "T4",
				Message:    "work package realizes no contract (CTR) or requirement (REQ)",
			})
		}
	}

	for _, s := range sortedSpecs(c.Specs) {
		if prefixOf(s.WorkPackage) != "WP" {
			diags = append(diags, Diagnostic{
				File:       s.Path,
				DocumentID: s.DocID,
				Rule:       "T4",
				Message:    fmt.Sprintf("specification must cite exactly one work package; got %q", s.WorkPackage),
			})
		}
		if prefixOf(s.Contract) != "CTR" {
			diags = append(diags, Diagnostic{
				File:       s.Path,
				DocumentID: s.DocID,
				Rule:       "T4",
				Message:    fmt.Sprintf("specification must cite exactly one contract; got %q", s.Contract),
			})
		}
	}
	return diags
}

// realizesContractOrReq reports whether any realizes target is a CTR or REQ id.
func realizesContractOrReq(targets []string) bool {
	for _, t := range targets {
		switch prefixOf(t) {
		case "CTR", "REQ":
			return true
		}
	}
	return false
}

// realizesAdjacency builds the realizes-edge adjacency list (source id -> target
// ids), used for transitive reachability in T3 and T6.
func (c *Corpus) realizesAdjacency() map[string][]string {
	adj := map[string][]string{}
	for _, e := range c.Edges {
		if e.Type == "realizes" && !isExternalReference(e.To) {
			adj[e.From] = append(adj[e.From], e.To)
		}
	}
	return adj
}

// reachesProduct reports whether `start` can reach any product-tier item by
// following realizes edges (including start itself if it is product-tier, which
// never happens for the T3 caller).
func reachesProduct(start string, adj map[string][]string, items map[string]*Item) bool {
	seen := map[string]bool{}
	var dfs func(id string) bool
	dfs = func(id string) bool {
		if seen[id] {
			return false
		}
		seen[id] = true
		if it, ok := items[id]; ok && !it.IsDocument && it.Tier == TierProduct {
			return true
		}
		for _, next := range adj[id] {
			if dfs(next) {
				return true
			}
		}
		return false
	}
	// Start must traverse at least one realizes edge to count (a bare arch item
	// with no edges fails); we seed from start's neighbours but also allow start
	// itself to be product (defensive, never true here).
	if it, ok := items[start]; ok && it.Tier == TierProduct && !it.IsDocument {
		return true
	}
	seen[start] = true
	for _, next := range adj[start] {
		if dfs(next) {
			return true
		}
	}
	return false
}

// sortDiagnostics orders diagnostics deterministically by file, then rule, then
// document id, then message.
func sortDiagnostics(diags []Diagnostic) []Diagnostic {
	sort.SliceStable(diags, func(i, j int) bool {
		a, b := diags[i], diags[j]
		if a.File != b.File {
			return a.File < b.File
		}
		if a.Rule != b.Rule {
			return a.Rule < b.Rule
		}
		if a.DocumentID != b.DocumentID {
			return a.DocumentID < b.DocumentID
		}
		return a.Message < b.Message
	})
	return diags
}

func sortedItemIDs(items map[string]*Item) []string {
	ids := make([]string, 0, len(items))
	for id := range items {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

func sortedSpecs(specs []SpecCite) []SpecCite {
	out := make([]SpecCite, len(specs))
	copy(out, specs)
	sort.SliceStable(out, func(i, j int) bool { return out[i].Path < out[j].Path })
	return out
}
