package render

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/helios/poc/knowledge/internal/rule"
)

func loadRules(t *testing.T) []rule.Rule {
	t.Helper()
	rules, err := rule.LoadDir(filepath.Join("..", "..", "rules"))
	if err != nil {
		t.Fatalf("load rules: %v", err)
	}
	return rules
}

// TestRenderIsPure: same DB in, byte-identical artifacts out.
func TestRenderIsPure(t *testing.T) {
	rules := loadRules(t)
	if Guide(rules) != Guide(rules) || Core(rules) != Core(rules) {
		t.Fatal("render is not a pure function of the rule DB")
	}
}

// TestGuideContainsEveryRule: the monolithic arm must carry the whole DB.
func TestGuideContainsEveryRule(t *testing.T) {
	rules := loadRules(t)
	guide := Guide(rules)
	for _, r := range rules {
		if !strings.Contains(guide, r.ID) {
			t.Errorf("GUIDE.md missing rule %s", r.ID)
		}
	}
}

// TestCoreCompactness: the hybrid core must stay within its token budget
// (~1k tokens ≈ 4KB) — compression pressure is an anti-slop invariant.
func TestCoreCompactness(t *testing.T) {
	core := Core(loadRules(t))
	if len(core) > 4096 {
		t.Fatalf("CORE.md is %d bytes; budget is 4096 — slop dies under a budget", len(core))
	}
	// Every post-cutoff rule must still be present (that's the high-delta knowledge).
	for _, id := range []string{"go/errors-astype", "go/slog-multihandler", "go/benchmark-loop", "go/waitgroup-go"} {
		if !strings.Contains(core, id) {
			t.Errorf("CORE.md missing post-cutoff rule %s", id)
		}
	}
}
