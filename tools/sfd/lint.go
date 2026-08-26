package main

// sfd graph lint — the 26 rules of the P0/P1 lint contract, as shipped
// code. The contract lives in docs/sfd/30-p0-graph.yaml (lint:) and
// docs/sfd/40-p1-registry.yaml (lint:); rule ids G1-G17 / R2-R10 follow
// the refutation record (2026-08-26) so every rule traces to the tamper
// that proved it can fail. Records are parsed as raw maps: the key-oracle
// rules need actual keys, not struct fields.

import (
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

// Finding is one lint violation. Rule carries the contract id.
type Finding struct {
	Rule string
	Msg  string
}

func (f Finding) String() string { return f.Rule + ": " + f.Msg }

// rawDoc is a YAML document parsed as generic maps.
type rawDoc = map[string]any

func loadYAMLMap(path string) (rawDoc, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc rawDoc
	if err := yaml.Unmarshal(raw, &doc); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return doc, nil
}

func asList(v any) []any {
	l, _ := v.([]any)
	return l
}

func asMap(v any) map[string]any {
	m, _ := v.(map[string]any)
	return m
}

func asStr(v any) string {
	s, _ := v.(string)
	return s
}

func strList(v any) []string {
	var out []string
	for _, item := range asList(v) {
		out = append(out, fmt.Sprintf("%v", item))
	}
	return out
}

// LintGraph runs the full contract against a parsed graph + registry.
func LintGraph(graph, registry rawDoc) []Finding {
	var fs []Finding
	add := func(rule, format string, args ...any) {
		fs = append(fs, Finding{Rule: rule, Msg: fmt.Sprintf(format, args...)})
	}

	questions := asList(graph["questions"])
	adaptive := asList(graph["adaptive"])
	metrics := asList(asMap(registry)["metrics"])

	// index the graph
	qids := map[string]bool{}
	values := map[string][]string{} // question id -> values
	tiers := map[string]string{}
	allValues := map[string]bool{}
	for _, qa := range append(append([]any{}, questions...), adaptive...) {
		q := asMap(qa)
		id := asStr(q["id"])
		qids[id] = true
		values[id] = strList(q["values"])
		tiers[id] = asStr(q["tier"])
		for _, v := range values[id] {
			allValues[v] = true
		}
	}
	pirFields := map[string]bool{}
	for _, f := range strList(graph["pir_fields"]) {
		pirFields[f] = true
	}
	metricIDs := map[string]bool{}
	for _, ma := range metrics {
		metricIDs[asStr(asMap(ma)["id"])] = true
	}
	derivations := asMap(graph["derivations"])

	// G15: unique ids (count over the raw lists, qids dedups)
	seen := map[string]int{}
	for _, qa := range append(append([]any{}, questions...), adaptive...) {
		seen[asStr(asMap(qa)["id"])]++
	}
	for id, n := range seen {
		if n > 1 {
			add("G15", "id %s declared %d times", id, n)
		}
	}

	// per-record rules
	fedMetrics := map[string]bool{}
	producedFields := map[string]bool{}
	requiredFeeders := map[string]bool{} // pir field -> fed by required question
	openTargets := map[string]bool{}

	checkRecord := func(q map[string]any, kind string, keyOracle map[string]any) {
		id := asStr(q["id"])
		req := strList(keyOracle["required"])
		opt := strList(keyOracle["optional"])
		allowed := map[string]bool{}
		for _, k := range append(append([]string{}, req...), opt...) {
			allowed[k] = true
		}
		// G14: key oracle — missing required, unknown keys
		for _, k := range req {
			if _, ok := q[k]; !ok {
				add("G14", "%s %s missing required key %q", kind, id, k)
			}
		}
		for k := range q {
			if !allowed[k] {
				add("G14", "%s %s unknown key %q", kind, id, k)
			}
		}
		// G16: feeds non-empty
		feeds := strList(q["feeds"])
		if len(feeds) == 0 {
			add("G16", "%s %s has empty or absent feeds — a question feeding nothing is dead", kind, id)
		}
		// G1: per-feed home
		for _, f := range feeds {
			switch {
			case strings.HasPrefix(f, "metric."):
				fedMetrics[f] = true
				if !metricIDs[f] {
					add("G1", "%s %s feeds unregistered metric %s", kind, id, f)
				}
			default:
				producedFields[f] = true
				if !pirFields[f] {
					add("G1", "%s %s feeds unknown pir field %s", kind, id, f)
				}
				if asStr(q["tier"]) == "required" {
					requiredFeeders[f] = true
				}
			}
		}
		// G17: values iff enum/multi
		typ := asStr(q["type"])
		hasVals := len(strList(q["values"])) > 0
		if (typ == "enum" || typ == "multi") && !hasVals {
			add("G17", "%s %s type %s without values — unanswerable", kind, id, typ)
		}
		if typ != "enum" && typ != "multi" && hasVals {
			add("G17", "%s %s type %s carries values — a lie", kind, id, typ)
		}
		// G5: values are strings
		for _, item := range asList(q["values"]) {
			if _, ok := item.(string); !ok {
				add("G5", "%s %s value %v is not a YAML string (quote YAML-1.1 booleans)", kind, id, item)
			}
		}
		// G4 + opens collection
		vals := map[string]bool{}
		for _, v := range strList(q["values"]) {
			vals[v] = true
		}
		for k, tgt := range asMap(q["opens"]) {
			if !vals[k] {
				add("G4", "%s opens key %q is not one of its values", id, k)
			}
			for _, t := range strList(tgt) {
				if !qids[t] {
					add("G3", "%s opens unknown question %s", id, t)
				}
				openTargets[t] = true
			}
		}
		// G12: glosses keys
		for k := range asMap(q["glosses"]) {
			if !vals[k] {
				add("G12", "%s gloss key %q is not one of its values", id, k)
			}
		}
		// G9: per-question adaptive ref
		if aref := asStr(q["adaptive"]); kind == "question" && aref != "" {
			found := false
			for _, aa := range adaptive {
				if asStr(asMap(aa)["id"]) == aref {
					found = true
				}
			}
			if !found {
				add("G9", "%s adaptive ref %s not declared in the adaptive block", id, aref)
			}
		}
		// G13: routing
		if kind == "adaptive" {
			spawned := map[string]bool{}
			for _, s := range strList(q["spawned_by"]) {
				spawned[s] = true
			}
			feedSet := map[string]bool{}
			for _, f := range feeds {
				feedSet[f] = true
			}
			for src, tgt := range asMap(q["routing"]) {
				if !spawned[src] {
					add("G13", "%s routing source %s not in spawned_by", id, src)
				}
				t := asStr(tgt)
				if !feedSet[t] || !pirFields[t] {
					add("G13", "%s routing target %s is not one of its feeds and a pir field", id, t)
				}
			}
		}
	}

	for _, qa := range questions {
		checkRecord(asMap(qa), "question", asMap(graph["question_keys"]))
	}
	for _, aa := range adaptive {
		checkRecord(asMap(aa), "adaptive", asMap(graph["adaptive_keys"]))
	}

	// G3: conditional_questions == opens targets, set equality
	declared := map[string]bool{}
	for _, c := range strList(graph["conditional_questions"]) {
		declared[c] = true
	}
	for t := range openTargets {
		if !declared[t] {
			add("G3", "%s is an opens target but not in conditional_questions — silently conditional", t)
		}
	}
	for d := range declared {
		if !openTargets[d] {
			add("G3", "%s declared conditional but no opens edge targets it", d)
		}
	}

	// G2: every registry metric referenced
	for m := range metricIDs {
		if !fedMetrics[m] {
			add("G2", "registry metric %s is fed by no question — unanswerable", m)
		}
	}

	// derivations: G7 maps exact, G11 rule refs; derived fields count as produced
	qidRe := regexp.MustCompile(`q\.[a-z_.]+[a-z]`)
	for name, da := range derivations {
		d := asMap(da)
		if from := asStr(d["from"]); from != "" {
			if !qids[from] {
				add("G7", "derivation %s from unknown question %s", name, from)
				continue
			}
			if strings.HasPrefix(name, "pir.") {
				producedFields[name] = true
				if tiers[from] == "required" {
					requiredFeeders[name] = true
				}
			}
			mp := asMap(d["map"])
			srcVals := map[string]bool{}
			for _, v := range values[from] {
				srcVals[v] = true
			}
			for k := range mp {
				if !srcVals[k] {
					add("G7", "derivation %s maps unknown value %q", name, k)
				}
			}
			for v := range srcVals {
				if _, ok := mp[v]; !ok {
					add("G7", "derivation %s misses value %q of %s", name, v, from)
				}
			}
		}
		if rule := asStr(d["rule"]); rule != "" {
			for _, ref := range qidRe.FindAllString(rule, -1) {
				if !qids[ref] {
					add("G11", "derivation %s references unknown question %s", name, ref)
				}
			}
		}
	}

	// G8: consistency refs
	for _, ca := range asList(graph["consistency"]) {
		c := asMap(ca)
		id := asStr(c["id"])
		for _, ref := range qidRe.FindAllString(asStr(c["red_when"]), -1) {
			if !qids[ref] {
				add("G8", "consistency %s references unknown question %s", id, ref)
			}
		}
	}

	// G10: every pir_fields produced
	for f := range pirFields {
		if !producedFields[f] {
			add("G10", "pir field %s is produced by no feed or derivation", f)
		}
	}

	// G6: required pir fields fed by required questions/derivations
	for _, f := range strList(graph["pir_required"]) {
		if !requiredFeeders[f] {
			add("G6", "required pir field %s is not fed by any required-tier question or derivation", f)
		}
	}

	// ── registry rules ────────────────────────────────────────────────
	regKeys := map[string]bool{
		"id": true, "asks": true, "fed_by": true, "consumer": true,
		"verdict_weight": true, "scored_by": true, "scale": true,
		"absent_when": true, "human_gate_when": true,
	}
	backtick := regexp.MustCompile("`([^`]+)`")
	mseen := map[string]int{}
	for _, ma := range metrics {
		m := asMap(ma)
		id := asStr(m["id"])
		mseen[id]++
		// R8: closed key list
		for k := range m {
			if !regKeys[k] {
				add("R8", "metric %s unknown key %q", id, k)
			}
		}
		// R10: fed_by non-empty
		fedBy := strList(m["fed_by"])
		if len(fedBy) == 0 {
			add("R10", "metric %s has empty or absent fed_by", id)
		}
		// R2: fed_by valid
		allCondOrAdaptive := len(fedBy) > 0
		for _, q := range fedBy {
			if !qids[q] {
				add("R2", "metric %s fed_by unknown question %s", id, q)
			}
			isAdaptive := false
			for _, aa := range adaptive {
				if asStr(asMap(aa)["id"]) == q {
					isAdaptive = true
				}
			}
			if !openTargets[q] && !isAdaptive {
				allCondOrAdaptive = false
			}
		}
		// R7: absent_when when every feed conditional/adaptive
		if allCondOrAdaptive {
			if asStr(m["absent_when"]) == "" {
				add("R7", "metric %s: every fed_by is conditional or adaptive but no absent_when", id)
			}
		}
		// R4: consumer
		consumer := asStr(m["consumer"])
		if consumer != "P1-verdict" && consumer != "P2-class" {
			add("R4", "metric %s consumer %q invalid", id, consumer)
		}
		// R5: verdict_weight iff P1-verdict
		_, hasWeight := m["verdict_weight"]
		if (consumer == "P1-verdict") != hasWeight {
			add("R5", "metric %s verdict_weight presence wrong for consumer %s", id, consumer)
		}
		// R6: scale complete
		scale := asMap(m["scale"])
		for _, lvl := range []string{"green", "amber", "red"} {
			if asStr(scale[lvl]) == "" {
				add("R6", "metric %s scale missing %s", id, lvl)
			}
		}
		// R9: backticked scale tokens are graph values
		for lvl, txt := range scale {
			for _, mch := range backtick.FindAllStringSubmatch(asStr(txt), -1) {
				if !allValues[mch[1]] {
					add("R9", "metric %s scale %s backticks %q — not a graph value", id, lvl, mch[1])
				}
			}
		}
	}
	// R3: unique metric ids
	for id, n := range mseen {
		if n > 1 {
			add("R3", "metric id %s declared %d times", id, n)
		}
	}

	sort.Slice(fs, func(i, j int) bool {
		if fs[i].Rule != fs[j].Rule {
			return fs[i].Rule < fs[j].Rule
		}
		return fs[i].Msg < fs[j].Msg
	})
	return fs
}
