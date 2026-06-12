// rulecheck runs every compiled rule oracle against a Go module directory.
//
// Modes:
//
//	rulecheck -dir . -format text -rules /path/to/rules   # agent-facing (check.sh): hints included
//	rulecheck -dir . -format json                         # scorer-facing: stable JSON
//
// Exit codes: 0 = no violations, 1 = violations found, 2 = error.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/helios/poc/knowledge/internal/check"
	"github.com/helios/poc/knowledge/internal/rule"
)

func main() {
	dir := flag.String("dir", ".", "module directory to analyze")
	format := flag.String("format", "text", "output format: text | json")
	rulesDir := flag.String("rules", "", "rules directory (enables fix hints in text output)")
	transitive := flag.Bool("transitive", false, "v2 constructor-purity: package-local call-graph fixpoint")
	flag.Parse()

	violations, err := check.RunWithOptions(*dir, check.All(), check.Options{TransitivePurity: *transitive})
	if err != nil {
		fmt.Fprintf(os.Stderr, "rulecheck: %v\n", err)
		os.Exit(2)
	}

	switch *format {
	case "json":
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(struct {
			Violations []check.Violation `json:"violations"`
		}{Violations: violations}); err != nil {
			fmt.Fprintf(os.Stderr, "rulecheck: %v\n", err)
			os.Exit(2)
		}
	case "text":
		hints := map[string]string{}
		if *rulesDir != "" {
			rules, err := rule.LoadDir(*rulesDir)
			if err != nil {
				fmt.Fprintf(os.Stderr, "rulecheck: load rules: %v\n", err)
				os.Exit(2)
			}
			for _, r := range rules {
				hints[r.ID] = r.FixHint
			}
		}
		for _, v := range violations {
			fmt.Printf("%s: [%s] %s\n", v.Pos, v.Rule, v.Message)
			if hint := hints[v.Rule]; hint != "" {
				fmt.Printf("    fix: %s\n", hint)
			}
		}
		if len(violations) == 0 {
			fmt.Println("rulecheck: all rules satisfied")
		} else {
			fmt.Printf("rulecheck: %d violation(s)\n", len(violations))
		}
	default:
		fmt.Fprintf(os.Stderr, "rulecheck: unknown format %q\n", *format)
		os.Exit(2)
	}

	if len(violations) > 0 {
		os.Exit(1)
	}
}
