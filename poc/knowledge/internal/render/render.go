// Package render compiles the rule DB into the consumption artifacts of each
// arm. Rendering is a pure function of the DB: same rules in, byte-identical
// artifacts out.
package render

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/helios/poc/knowledge/internal/rule"
)

// Guide renders the monolithic arm artifact: every rule in full prose.
func Guide(rules []rule.Rule) string {
	var b strings.Builder
	b.WriteString("# Go knowledge base — full guide\n\n")
	b.WriteString("You are writing Go (toolchain 1.26). Every rule below is mandatory unless one of its listed exceptions applies.\n\n")
	for _, r := range rules {
		fmt.Fprintf(&b, "## %s\n\n", r.ID)
		fmt.Fprintf(&b, "**Rule.** %s\n\n", strings.TrimSpace(r.Statement))
		fmt.Fprintf(&b, "**Why.** %s\n\n", strings.TrimSpace(r.Rationale))
		fmt.Fprintf(&b, "**Applies when.** %s\n\n", strings.TrimSpace(r.Applicability))
		b.WriteString("**Exceptions.**\n")
		for _, e := range r.Exceptions {
			fmt.Fprintf(&b, "- %s\n", strings.TrimSpace(e))
		}
		b.WriteString("\n**Do.**\n```go\n")
		b.WriteString(strings.TrimRight(r.Example.Good, "\n"))
		b.WriteString("\n```\n\n**Don't.**\n```go\n")
		b.WriteString(strings.TrimRight(r.Example.Bad, "\n"))
		b.WriteString("\n```\n\n")
	}
	return b.String()
}

// Core renders the hybrid arm artifact: a compact always-in-context core.
// One line per established rule; short Do-snippets only for the post-cutoff
// rules (the knowledge the model cannot have).
func Core(rules []rule.Rule) string {
	var b strings.Builder
	b.WriteString("# Go knowledge core (toolchain 1.26)\n\n")
	b.WriteString("Mandatory rules. The deterministic checker (`bash ./check.sh`) enforces all of them — run it and fix findings until it exits 0.\n\n")
	for _, r := range rules {
		if r.Category == rule.CategoryPostCutoff {
			continue
		}
		fmt.Fprintf(&b, "- **%s** — %s\n", r.ID, strings.TrimSpace(r.Statement))
	}
	b.WriteString("\n## Go 1.24–1.26 APIs you must use (newer than your training data)\n\n")
	for _, r := range rules {
		if r.Category != rule.CategoryPostCutoff {
			continue
		}
		fmt.Fprintf(&b, "- **%s** (Go %s+) — %s\n```go\n%s\n```\n",
			r.ID, r.Staleness.GoMinimum, strings.TrimSpace(r.Statement), strings.TrimRight(r.Example.Good, "\n"))
	}
	return b.String()
}

// CheckScript renders the workspace check.sh used by the checker and hybrid
// arms. rulecheckBinary and rulesDir are absolute paths recorded in the run
// provenance.
func CheckScript(rulecheckBinary, rulesDir string) string {
	return fmt.Sprintf(`#!/bin/bash
# Deterministic quality gate. Exit 0 = all green. Fix every finding.
set -o pipefail
status=0
go build ./... || status=1
go vet ./... || status=1
%s -dir . -format text -rules %s || status=1
exit $status
`, rulecheckBinary, rulesDir)
}

// WriteArtifacts writes the rendered artifacts under armsDir.
func WriteArtifacts(armsDir string, rules []rule.Rule) error {
	files := map[string]string{
		filepath.Join(armsDir, "monolithic", "GUIDE.md"): Guide(rules),
		filepath.Join(armsDir, "hybrid", "CORE.md"):      Core(rules),
	}
	for path, content := range files {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			return err
		}
	}
	return nil
}
