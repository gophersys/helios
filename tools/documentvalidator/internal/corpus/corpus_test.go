package corpus

import (
	"testing"

	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// doc builds a projection.Document inline for corpus tests.
func doc(path, docType string, projn map[string]any) *projection.Document {
	return &projection.Document{Path: path, DocumentType: docType, Projection: projn}
}

func meta(id, typ string, links map[string]any) map[string]any {
	m := map[string]any{"id": id, "type": typ}
	if links != nil {
		m["links"] = links
	}
	return m
}

// buildCorpus is a tiny, valid two-tier corpus: one persona, one requirement
// realizing it, one component realizing the requirement.
func buildCorpus() *Corpus {
	charter := doc("charter.md", "product-charter", map[string]any{
		"meta": meta("product-charter", "product-charter", nil),
		"data": map[string]any{
			"personas": []any{map[string]any{"id": "PER-0001"}},
		},
	})
	reqs := doc("requirements.yaml", "requirements", map[string]any{
		"meta": meta("requirements", "requirements", nil),
		"data": map[string]any{
			"items": []any{map[string]any{
				"id":       "REQ-0001",
				"priority": "P1",
				"links":    map[string]any{"realizes": []any{"PER-0001"}},
			}},
		},
	})
	sysd := doc("system-design.yaml", "system-design", map[string]any{
		"meta": meta("system-design", "system-design", nil),
		"data": map[string]any{
			"components": []any{map[string]any{
				"id":    "CMP-0001",
				"links": map[string]any{"realizes": []any{"REQ-0001"}},
			}},
		},
	})
	return Build([]*projection.Document{charter, reqs, sysd})
}

func TestCleanCorpusHasNoViolations(t *testing.T) {
	c := buildCorpus()
	if diags := c.CheckAll(); len(diags) != 0 {
		t.Fatalf("expected no violations, got %d: %+v", len(diags), diags)
	}
}

func TestT1Dangling(t *testing.T) {
	reqs := doc("requirements.yaml", "requirements", map[string]any{
		"meta": meta("requirements", "requirements", nil),
		"data": map[string]any{
			"items": []any{map[string]any{
				"id":    "REQ-0001",
				"links": map[string]any{"realizes": []any{"PER-9999"}},
			}},
		},
	})
	c := Build([]*projection.Document{reqs})
	if !hasRule(c.CheckAll(), "T1") {
		t.Fatal("expected T1 for dangling PER-9999")
	}
}

func TestT2Direction(t *testing.T) {
	// A requirement (rank 1) realizing a component (rank 5) is downstream.
	reqs := doc("requirements.yaml", "requirements", map[string]any{
		"meta": meta("requirements", "requirements", nil),
		"data": map[string]any{
			"items": []any{map[string]any{
				"id":    "REQ-0001",
				"links": map[string]any{"realizes": []any{"CMP-0001"}},
			}},
		},
	})
	sysd := doc("system-design.yaml", "system-design", map[string]any{
		"meta": meta("system-design", "system-design", nil),
		"data": map[string]any{
			"components": []any{map[string]any{"id": "CMP-0001"}},
		},
	})
	c := Build([]*projection.Document{reqs, sysd})
	if !hasRule(c.CheckAll(), "T2") {
		t.Fatal("expected T2 for downstream realizes")
	}
}

func TestT2RefinesSameTierAllowed(t *testing.T) {
	// REQ-0002 refines REQ-0001 (same rank) — allowed.
	reqs := doc("requirements.yaml", "requirements", map[string]any{
		"meta": meta("requirements", "requirements", nil),
		"data": map[string]any{
			"items": []any{
				map[string]any{"id": "REQ-0001"},
				map[string]any{"id": "REQ-0002", "links": map[string]any{"refines": []any{"REQ-0001"}}},
			},
		},
	})
	c := Build([]*projection.Document{reqs})
	if hasRule(c.CheckAll(), "T2") {
		t.Fatal("refines within a tier should be allowed (no T2)")
	}
}

func TestT3ArchitectureWithoutProduct(t *testing.T) {
	// CMP-0001 has no realizes edge — unmotivated architecture.
	sysd := doc("system-design.yaml", "system-design", map[string]any{
		"meta": meta("system-design", "system-design", nil),
		"data": map[string]any{
			"components": []any{map[string]any{"id": "CMP-0001"}},
		},
	})
	c := Build([]*projection.Document{sysd})
	if !hasRule(c.CheckAll(), "T3") {
		t.Fatal("expected T3 for component with no product realizes")
	}
}

func TestT4WorkPackageAndSpec(t *testing.T) {
	// WP-0001 realizes nothing -> T4; spec cites a non-WP work_package -> T4.
	plan := doc("implementation-plan.yaml", "implementation-plan", map[string]any{
		"meta": meta("implementation-plan", "implementation-plan", nil),
		"data": map[string]any{
			"packages": []any{map[string]any{"id": "WP-0001"}},
		},
	})
	spec := doc("spec-0001.yaml", "specification", map[string]any{
		"meta": meta("spec-0001", "specification", nil),
		"data": map[string]any{"work_package": "REQ-0001", "contract": "CTR-0001"},
	})
	c := Build([]*projection.Document{plan, spec})
	if !hasRule(c.CheckAll(), "T4") {
		t.Fatal("expected T4 for unmotivated WP and bad spec citation")
	}
}

func TestT5Duplicate(t *testing.T) {
	reqs := doc("requirements.yaml", "requirements", map[string]any{
		"meta": meta("requirements", "requirements", nil),
		"data": map[string]any{
			"items": []any{
				map[string]any{"id": "REQ-0001"},
				map[string]any{"id": "REQ-0001"},
			},
		},
	})
	c := Build([]*projection.Document{reqs})
	if !hasRule(c.CheckAll(), "T5") {
		t.Fatal("expected T5 for duplicate REQ-0001")
	}
}

func TestT6Coverage(t *testing.T) {
	// A P1 requirement with no spec path is reported by T6 (but not by CheckAll).
	charter := doc("charter.md", "product-charter", map[string]any{
		"meta": meta("product-charter", "product-charter", nil),
		"data": map[string]any{"personas": []any{map[string]any{"id": "PER-0001"}}},
	})
	reqs := doc("requirements.yaml", "requirements", map[string]any{
		"meta": meta("requirements", "requirements", nil),
		"data": map[string]any{
			"items": []any{map[string]any{
				"id": "REQ-0001", "priority": "P1",
				"links": map[string]any{"realizes": []any{"PER-0001"}},
			}},
		},
	})
	c := Build([]*projection.Document{charter, reqs})
	if hasRule(c.CheckAll(), "T6") {
		t.Fatal("T6 must not appear in CheckAll (it is a report, not a violation)")
	}
	if !hasRule(c.CoverageReport(), "T6") {
		t.Fatal("expected T6 in coverage report for uncovered P1 requirement")
	}
}

func TestExternalReferencesSkipped(t *testing.T) {
	brief := doc("design-brief.md", "design-brief", map[string]any{
		"meta": meta("design-brief", "design-brief", map[string]any{
			"informs": []any{"artifact://design-system/x/theme"},
		}),
		"data": map[string]any{"design_system_reference": "artifact://design-system/x/theme"},
	})
	c := Build([]*projection.Document{brief})
	for _, d := range c.CheckAll() {
		if d.Rule == "T1" {
			t.Fatalf("external artifact:// reference should be skipped by T1, got %+v", d)
		}
	}
}

func hasRule(diags []Diagnostic, rule string) bool {
	for _, d := range diags {
		if d.Rule == rule {
			return true
		}
	}
	return false
}
