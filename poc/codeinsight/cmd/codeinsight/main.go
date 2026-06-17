// Command codeinsight points the analyzer at a git repository and prints its Report as
// JSON — the producer side of the "point Eden at a codebase → dashboards" feature.
//
// Usage:
//
//	codeinsight [flags] <repository-path>
//
// With --summary it prints a human-readable digest (top hotspots, strongest couplings,
// rating) instead of the full JSON payload — useful for the self-feeding smoke run.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/gophersys/poc/codeinsight"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "codeinsight:", err)
		os.Exit(1)
	}
}

func run() error {
	var (
		since      = flag.String("since", "", "git --since window bound (e.g. \"6 months ago\"); empty = full history")
		until      = flag.String("until", "", "git --until window bound")
		minShared  = flag.Int("coupling-min-shared", 3, "minimum shared revisions for a coupling edge")
		maxEntity  = flag.Int("max-entities", 0, "cap entities emitted by hotspot rank (0 = all)")
		maxCouple  = flag.Int("max-couplings", 0, "cap coupling edges emitted by degree (0 = all)")
		identifier = flag.String("identifier", "", "logical repository name (default: directory base)")
		summary    = flag.Bool("summary", false, "print a human-readable digest instead of JSON")
	)
	flag.Usage = func() {
		fmt.Fprintln(os.Stderr, "usage: codeinsight [flags] <repository-path>")
		flag.PrintDefaults()
	}
	flag.Parse()
	if flag.NArg() != 1 {
		flag.Usage()
		return fmt.Errorf("exactly one repository path is required")
	}

	report, err := codeinsight.Analyze(context.Background(), codeinsight.Config{
		RepositoryPath:    flag.Arg(0),
		Identifier:        *identifier,
		Since:             *since,
		Until:             *until,
		CouplingMinShared: *minShared,
		MaxEntities:       *maxEntity,
		MaxCouplings:      *maxCouple,
	})
	if err != nil {
		return err
	}

	if *summary {
		printDigest(report)
		return nil
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	return encoder.Encode(report)
}

func printDigest(report *codeinsight.Report) {
	fmt.Printf("Repository: %s @ %.12s\n", report.Repository.Identifier, report.Repository.HeadCommit)
	fmt.Printf("Window: %d commits (%.12s..%.12s)\n",
		report.Window.Revisions, report.Window.FromCommit, report.Window.ToCommit)
	fmt.Printf("Entities: %d files, %d LOC | maintainability %s (debt ratio %.1f%%) | bus factor %d\n\n",
		report.Summary.EntityCount, report.Summary.Lines,
		report.Summary.MaintainabilityRating, report.Summary.TechnicalDebtRatio*100, report.Summary.BusFactor)

	fmt.Println("Top hotspots (change frequency × complexity):")
	for i, e := range report.Entities {
		if i >= 10 {
			break
		}
		fmt.Printf("  %5.3f  %-50s  changes=%-3d cyclo=%-3d MI=%-5.1f author=%s\n",
			e.HotspotScore, truncate(e.Path, 50), e.ChangeFrequency, e.Cyclomatic, e.Maintainability, e.PrimaryAuthor)
	}

	fmt.Println("\nStrongest logical couplings (files changing together):")
	for i, c := range report.Couplings {
		if i >= 10 {
			break
		}
		fmt.Printf("  %5.1f%%  %s  <->  %s  (shared=%d)\n",
			c.Degree, truncate(c.EntityA, 34), truncate(c.EntityB, 34), c.SharedRevs)
	}
}

func truncate(value string, max int) string {
	if len(value) <= max {
		return value
	}
	return "…" + value[len(value)-max+1:]
}
