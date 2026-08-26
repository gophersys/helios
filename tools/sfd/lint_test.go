package main

// The tamper battery IS the test suite: each case replays a tamper from
// the five refutation rounds (2026-08-26) against the SHIPPED graph and
// registry, and asserts the specific rule fires. Every rule must have a
// failing input; the shipped files must pass clean.

import (
	"strings"
	"testing"
)

const (
	graphPath    = "../../docs/sfd/30-p0-graph.yaml"
	registryPath = "../../docs/sfd/40-p1-registry.yaml"
)

func loadShipped(t *testing.T) (rawDoc, rawDoc) {
	t.Helper()
	g, err := loadYAMLMap(graphPath)
	if err != nil {
		t.Fatal(err)
	}
	r, err := loadYAMLMap(registryPath)
	if err != nil {
		t.Fatal(err)
	}
	return g, r
}

func question(t *testing.T, g rawDoc, id string) map[string]any {
	t.Helper()
	for _, qa := range asList(g["questions"]) {
		if asStr(asMap(qa)["id"]) == id {
			return asMap(qa)
		}
	}
	t.Fatalf("fixture question %s not found", id)
	return nil
}

func metric(t *testing.T, r rawDoc, id string) map[string]any {
	t.Helper()
	for _, ma := range asList(r["metrics"]) {
		if asStr(asMap(ma)["id"]) == id {
			return asMap(ma)
		}
	}
	t.Fatalf("fixture metric %s not found", id)
	return nil
}

func assertRule(t *testing.T, findings []Finding, rule, needle string) {
	t.Helper()
	for _, f := range findings {
		if f.Rule == rule && strings.Contains(f.Msg, needle) {
			return
		}
	}
	t.Fatalf("expected %s finding containing %q, got %v", rule, needle, findings)
}

// The shipped files pass every rule. This is the green anchor: if THIS
// fails, either the contract or the implementation drifted.
func TestLintShippedFilesClean(t *testing.T) {
	g, r := loadShipped(t)
	if fs := LintGraph(g, r); len(fs) != 0 {
		t.Fatalf("shipped files must lint clean, got %d findings:\n%v", len(fs), fs)
	}
}

func TestTamperBattery(t *testing.T) {
	cases := []struct {
		name   string
		rule   string
		needle string
		mutate func(t *testing.T, g, r rawDoc)
	}{
		{"T1 stray question key", "G14", "colour", func(t *testing.T, g, r rawDoc) {
			question(t, g, "q.intent.who")["colour"] = "green"
		}},
		{"T2 missing mandatory key", "G14", "section", func(t *testing.T, g, r rawDoc) {
			delete(question(t, g, "q.intent.who"), "section")
		}},
		{"T5 unknown metric key", "R8", "priority", func(t *testing.T, g, r rawDoc) {
			metric(t, r, "metric.risk.privacy")["priority"] = 1
		}},
		{"T6 backticked non-value", "R9", "indoors-only", func(t *testing.T, g, r rawDoc) {
			metric(t, r, "metric.feasibility.env-risk")["scale"].(map[string]any)["green"] = "fine for `indoors-only` products"
		}},
		{"T7 round-1 recurrence: opens onto unconditional safety", "G3", "q.comp.safety", func(t *testing.T, g, r rawDoc) {
			question(t, g, "q.env.body")["opens"] = map[string]any{"yes": []any{"q.comp.safety"}}
		}},
		{"T8 absent_when removed", "R7", "edge-autonomy", func(t *testing.T, g, r rawDoc) {
			delete(metric(t, r, "metric.platform.edge-autonomy"), "absent_when")
		}},
		{"T12 empty feeds on shared-field question", "G16", "q.fn.stores", func(t *testing.T, g, r rawDoc) {
			question(t, g, "q.fn.stores")["feeds"] = []any{}
		}},
		{"T13 enum without values", "G17", "q.phys.carry", func(t *testing.T, g, r rawDoc) {
			delete(question(t, g, "q.phys.carry"), "values")
		}},
		{"T14 text with values", "G17", "q.novel.hard", func(t *testing.T, g, r rawDoc) {
			question(t, g, "q.novel.hard")["values"] = []any{"a", "b"}
		}},
		{"T15 empty fed_by", "R10", "self-assessed", func(t *testing.T, g, r rawDoc) {
			metric(t, r, "metric.risk.self-assessed")["fed_by"] = []any{}
		}},
		{"unregistered metric in feeds", "G1", "metric.ghost", func(t *testing.T, g, r rawDoc) {
			q := question(t, g, "q.intent.what")
			q["feeds"] = append(asList(q["feeds"]), "metric.ghost.axis")
		}},
		{"unfed registry metric", "G2", "metric.viability.clarity", func(t *testing.T, g, r rawDoc) {
			q := question(t, g, "q.intent.what")
			q["feeds"] = []any{"pir.summary"}
		}},
		{"opens key not a value", "G4", "sideways", func(t *testing.T, g, r rawDoc) {
			q := question(t, g, "q.fn.talks")
			asMap(q["opens"])["sideways"] = []any{"q.fn.offline"}
		}},
		{"non-string enum value", "G5", "not a YAML string", func(t *testing.T, g, r rawDoc) {
			q := question(t, g, "q.comp.safety")
			q["values"] = []any{false, "minor", "serious"}
		}},
		{"required field loses its required feeder", "G6", "pir.modes", func(t *testing.T, g, r rawDoc) {
			question(t, g, "q.power.duty")["tier"] = "scoring"
		}},
		{"derivation map misses a value", "G7", "wall-power", func(t *testing.T, g, r rawDoc) {
			d := asMap(asMap(g["derivations"])["pir.power_class"])
			delete(asMap(d["map"]), "wall-power")
		}},
		{"consistency references ghost question", "G8", "q.ghost.rule", func(t *testing.T, g, r rawDoc) {
			c := asMap(asList(g["consistency"])[0])
			c["red_when"] = "q.ghost.rule == nothing"
		}},
		{"adaptive ref undeclared", "G9", "q.ghost.spawn", func(t *testing.T, g, r rawDoc) {
			question(t, g, "q.env.conditions")["adaptive"] = "q.ghost.spawn"
		}},
		{"orphan pir field", "G10", "pir.ghost", func(t *testing.T, g, r rawDoc) {
			g["pir_fields"] = append(asList(g["pir_fields"]), "pir.ghost")
		}},
		{"rule-style derivation ghost ref", "G11", "q.ghost.derive", func(t *testing.T, g, r rawDoc) {
			d := asMap(asMap(g["derivations"])["capability.time"])
			d["rule"] = "whenever q.ghost.derive == never"
		}},
		{"gloss key not a value", "G12", "warp-core", func(t *testing.T, g, r rawDoc) {
			q := question(t, g, "q.power.source")
			asMap(q["glosses"])["warp-core"] = "science fiction"
		}},
		{"T3 routing target not a feed", "G13", "pir.physical.carry", func(t *testing.T, g, r rawDoc) {
			for _, aa := range asList(g["adaptive"]) {
				a := asMap(aa)
				if asStr(a["id"]) == "q.followup.range" {
					asMap(a["routing"])["q.env.conditions"] = "pir.physical.carry"
				}
			}
		}},
		{"duplicate question id", "G15", "q.intent.what", func(t *testing.T, g, r rawDoc) {
			g["questions"] = append(asList(g["questions"]), map[string]any{
				"id": "q.intent.what", "section": "S1", "tier": "color", "mode": "fixed",
				"ask": "dup", "type": "text", "feeds": []any{"pir.summary"},
			})
		}},
		{"declared conditional without an opens edge", "G3", "q.fn.stores", func(t *testing.T, g, r rawDoc) {
			g["conditional_questions"] = append(asList(g["conditional_questions"]), "q.fn.stores")
		}},
		{"fed_by ghost question", "R2", "q.ghost.feed", func(t *testing.T, g, r rawDoc) {
			metric(t, r, "metric.viability.outcome")["fed_by"] = []any{"q.ghost.feed"}
		}},
		{"duplicate metric id", "R3", "metric.viability.clarity", func(t *testing.T, g, r rawDoc) {
			ms := asList(r["metrics"])
			r["metrics"] = append(ms, asMap(ms[0]))
		}},
		{"invalid consumer", "R4", "P9-nowhere", func(t *testing.T, g, r rawDoc) {
			metric(t, r, "metric.viability.clarity")["consumer"] = "P9-nowhere"
		}},
		{"verdict_weight on P2-class", "R5", "edge-autonomy", func(t *testing.T, g, r rawDoc) {
			metric(t, r, "metric.platform.edge-autonomy")["verdict_weight"] = "core"
		}},
		{"scale missing red", "R6", "metric.viability.outcome", func(t *testing.T, g, r rawDoc) {
			delete(asMap(metric(t, r, "metric.viability.outcome")["scale"]), "red")
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			g, r := loadShipped(t)
			tc.mutate(t, g, r)
			assertRule(t, LintGraph(g, r), tc.rule, tc.needle)
		})
	}
}
