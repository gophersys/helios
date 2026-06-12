// Package rule defines the knowledge-base rule schema and loader.
//
// A rule is the atomic unit of the knowledge base. Every rule must ship with
// an oracle (a deterministic checker for C1, a property test for C2, or a
// rubric for C3). A rule without an oracle is an opinion; an opinion without
// a citation is slop — both are rejected at load time.
package rule

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"gopkg.in/yaml.v3"
)

// Class is the checkability class of a rule.
type Class string

const (
	ClassDecidable Class = "C1" // deterministic static checker
	ClassProperty  Class = "C2" // property / conformance test
	ClassJudgment  Class = "C3" // rubric-anchored judge (non-deterministic; excluded from POC scoring)
)

// Category groups rules by where the knowledge comes from.
type Category string

const (
	CategoryArchitecture Category = "architecture" // helios architectural discipline
	CategoryIdiom        Category = "idiom"        // established Go idioms (expected in model priors)
	CategoryPostCutoff   Category = "post-cutoff"  // Go 1.24–1.26 era (expected absent from model priors)
)

// Example holds a compliant and a violating snippet. Both are mandatory:
// a rule whose author cannot produce a realistic violation is not falsifiable.
type Example struct {
	Good string `yaml:"good"`
	Bad  string `yaml:"bad"`
}

// Oracle binds the rule to its checker.
type Oracle struct {
	Kind string `yaml:"kind"` // "analyzer" for C1
	Ref  string `yaml:"ref"`  // analyzer name in internal/check
}

// Provenance cites the source span the rule was extracted from.
type Provenance struct {
	Source string `yaml:"source"`
	Tier   int    `yaml:"tier"` // 1 = spec/release notes, 2 = official docs, 3 = recognized book/talk, 4 = project doc
}

// Staleness bounds the rule's validity.
type Staleness struct {
	GoMinimum string `yaml:"go_minimum"`
	ReviewBy  string `yaml:"review_by"`
}

// Probe is an optional capability probe: a tool-less question that reveals
// whether the model *knows* the rule's knowledge at all, independent of
// whether it *applies* it while coding. Distinguishes "never knew" from
// "knew but ignored".
type Probe struct {
	Question string `yaml:"question"`
	// ExpectMarkers: the answer demonstrates the knowledge iff it contains at
	// least one marker (case-sensitive substring match).
	ExpectMarkers []string `yaml:"expect_markers"`
}

// Rule is one knowledge-base entry.
type Rule struct {
	ID            string       `yaml:"id"`
	Class         Class        `yaml:"class"`
	Category      Category     `yaml:"category"`
	Statement     string       `yaml:"statement"`
	Rationale     string       `yaml:"rationale"`
	Applicability string       `yaml:"applicability"`
	Exceptions    []string     `yaml:"exceptions"`
	Example       Example      `yaml:"example"`
	Oracle        Oracle       `yaml:"oracle"`
	FixHint       string       `yaml:"fix_hint"`
	Provenance    []Provenance `yaml:"provenance"`
	Staleness     Staleness    `yaml:"staleness"`
	Probe         *Probe       `yaml:"probe,omitempty"`
	Status        string       `yaml:"status"` // CANDIDATE | VERIFIED | COMPILED | PROVEN | DEPRECATED
	// HypothesisBaselineViolation is the pre-registered prediction of how often
	// the bare model violates this rule under temptation: "low" | "medium" | "high".
	// The experiment exists to confirm or refute it.
	HypothesisBaselineViolation string `yaml:"hypothesis_baseline_violation"`
}

// Validate enforces the anti-slop invariants.
func (r *Rule) Validate() error {
	switch {
	case r.ID == "":
		return fmt.Errorf("rule missing id")
	case r.Statement == "":
		return fmt.Errorf("rule %s: missing statement", r.ID)
	case r.Oracle.Ref == "":
		return fmt.Errorf("rule %s: missing oracle (a rule without an oracle is an opinion)", r.ID)
	case len(r.Provenance) == 0:
		return fmt.Errorf("rule %s: missing provenance (an opinion without a citation is slop)", r.ID)
	case r.Example.Good == "" || r.Example.Bad == "":
		return fmt.Errorf("rule %s: both good and bad examples are mandatory (falsifiability)", r.ID)
	case len(r.Exceptions) == 0:
		return fmt.Errorf("rule %s: at least one documented exception is mandatory (no unconditional platitudes)", r.ID)
	case r.Applicability == "":
		return fmt.Errorf("rule %s: missing applicability predicate", r.ID)
	}
	return nil
}

// LoadDir loads and validates every rule in dir, sorted by ID for determinism.
func LoadDir(dir string) ([]Rule, error) {
	entries, err := filepath.Glob(filepath.Join(dir, "*.yaml"))
	if err != nil {
		return nil, err
	}
	sort.Strings(entries)
	var rules []Rule
	for _, path := range entries {
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", path, err)
		}
		var r Rule
		if err := yaml.Unmarshal(data, &r); err != nil {
			return nil, fmt.Errorf("parse %s: %w", path, err)
		}
		if err := r.Validate(); err != nil {
			return nil, fmt.Errorf("%s: %w", path, err)
		}
		rules = append(rules, r)
	}
	if len(rules) == 0 {
		return nil, fmt.Errorf("no rules found in %s", dir)
	}
	return rules, nil
}

// ByID indexes rules.
func ByID(rules []Rule) map[string]Rule {
	m := make(map[string]Rule, len(rules))
	for _, r := range rules {
		m[r.ID] = r
	}
	return m
}
