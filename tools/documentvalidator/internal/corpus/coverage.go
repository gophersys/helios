package corpus

import "sort"

// CoverageReport implements T6 as a report (not an error): the P1 requirements
// that do not reach any specification through the graph. A requirement is
// covered when some specification's work package realizes — directly or through
// the realizes graph — that requirement. Returned in id order.
//
// The reachability is computed backwards from each specification: a spec cites
// one WP; that WP realizes contracts/requirements; following realizes edges from
// those targets fans out to every upstream item the spec's package serves. Any
// P1 requirement in that closure is covered.
func (c *Corpus) CoverageReport() []Diagnostic {
	covered := c.coveredRequirements()

	var diags []Diagnostic
	for _, id := range sortedItemIDs(c.Items) {
		item := c.Items[id]
		if item.Prefix != "REQ" || item.Priority != "P1" {
			continue
		}
		if !covered[id] {
			diags = append(diags, Diagnostic{
				File:       item.DefinedIn,
				DocumentID: id,
				Rule:       "T6",
				Message:    "P1 requirement reaches no specification through the graph (coverage gap)",
			})
		}
	}
	return diags
}

// coveredRequirements returns the set of requirement ids reachable from any
// specification through its work package and the realizes graph.
func (c *Corpus) coveredRequirements() map[string]bool {
	adj := c.realizesAdjacency()
	covered := map[string]bool{}

	for _, s := range c.Specs {
		if s.WorkPackage == "" {
			continue
		}
		// Seed the walk from the spec's WP and its cited contract: both are
		// upstream targets the spec realizes, and either may lead to a REQ.
		seeds := []string{s.WorkPackage}
		if s.Contract != "" {
			seeds = append(seeds, s.Contract)
		}
		seen := map[string]bool{}
		var walk func(id string)
		walk = func(id string) {
			if seen[id] {
				return
			}
			seen[id] = true
			if it, ok := c.Items[id]; ok && it.Prefix == "REQ" {
				covered[id] = true
			}
			for _, next := range adj[id] {
				walk(next)
			}
		}
		for _, seed := range seeds {
			walk(seed)
		}
	}
	return covered
}

// EdgeList returns the full link-edge list in stable order for the `links`
// command: by source path, then source id, then link type, then target.
func (c *Corpus) EdgeList() []Edge {
	out := make([]Edge, len(c.Edges))
	copy(out, c.Edges)
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i], out[j]
		if a.FromPath != b.FromPath {
			return a.FromPath < b.FromPath
		}
		if a.From != b.From {
			return a.From < b.From
		}
		if a.Type != b.Type {
			return a.Type < b.Type
		}
		return a.To < b.To
	})
	return out
}
