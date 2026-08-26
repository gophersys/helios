package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

const toolVersion = "sfd/v0"

func usage() {
	fmt.Fprintf(os.Stderr, `sfd — software-first-design catalog tool

usage:
  sfd component add <compatible> --zephyr <path> [--catalog <dir>] [--force]
  sfd soc       add <soc-name>   --zephyr <path> [--catalog <dir>] [--force] [--dtsi f1,f2]
  sfd verify                     --zephyr <path> [--catalog <dir>]

The identity of a component is its Zephyr compatible string; the identity
of a SoC is its Zephyr SoC name. Part numbers are a late binding (P4) and
are never written by this tool.
`)
	os.Exit(2)
}

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	var err error
	switch os.Args[1] {
	case "component":
		if len(os.Args) < 4 || os.Args[2] != "add" {
			usage()
		}
		err = cmdComponentAdd(os.Args[3], os.Args[4:])
	case "soc":
		if len(os.Args) < 4 || os.Args[2] != "add" {
			usage()
		}
		err = cmdSocAdd(os.Args[3], os.Args[4:])
	case "verify":
		err = cmdVerify(os.Args[2:])
	default:
		usage()
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "sfd: FAIL: %v\n", err)
		os.Exit(1)
	}
}

type commonFlags struct {
	zephyr  string
	catalog string
	force   bool
}

func parseCommon(fs *flag.FlagSet, args []string) (commonFlags, error) {
	var c commonFlags
	fs.StringVar(&c.zephyr, "zephyr", "", "path to the Zephyr tree (required)")
	fs.StringVar(&c.catalog, "catalog", "catalog", "catalog output directory")
	fs.BoolVar(&c.force, "force", false, "overwrite an existing record")
	if err := fs.Parse(args); err != nil {
		return c, err
	}
	if c.zephyr == "" {
		return c, fmt.Errorf("--zephyr is required")
	}
	return c, nil
}

func provenance(zephyrRoot string) (Provenance, error) {
	sha, err := ZephyrSHA(zephyrRoot)
	if err != nil {
		return Provenance{}, err
	}
	return Provenance{
		ZephyrSHA: sha,
		Extracted: time.Now().UTC().Format("2006-01-02"),
		Tool:      toolVersion,
	}, nil
}

// cmdComponentAdd implements PROPOSED → SOURCED. It refuses when Zephyr has
// no binding: that refusal is the process, the component becomes explicit
// driver-work instead of a hidden assumption.
func cmdComponentAdd(compatible string, args []string) error {
	c, err := parseCommon(flag.NewFlagSet("component add", flag.ExitOnError), args)
	if err != nil {
		return err
	}
	prov, err := provenance(c.zephyr)
	if err != nil {
		return err
	}
	rec, err := buildComponentRecord(c.zephyr, compatible)
	if err != nil {
		return err
	}
	rec.Provenance = prov
	path := componentPath(c.catalog, compatible)
	if err := writeRecord(path, rec, c.force); err != nil {
		return err
	}
	fmt.Printf("SOURCED %s → %s (depth %s, %d binding(s), %d driver dir(s), %d exerciser(s))\n",
		compatible, path, rec.Depth, len(rec.Bindings), len(rec.Drivers), len(rec.ExercisedBy))
	return nil
}

func cmdSocAdd(name string, args []string) error {
	fs := flag.NewFlagSet("soc add", flag.ExitOnError)
	var dtsiFlag string
	fs.StringVar(&dtsiFlag, "dtsi", "", "comma-separated dtsi paths (relative to the zephyr root) when discovery fails")
	c, err := parseCommon(fs, args)
	if err != nil {
		return err
	}
	prov, err := provenance(c.zephyr)
	if err != nil {
		return err
	}
	var seeds []string // nil = auto-discovery
	if dtsiFlag != "" {
		for _, p := range strings.Split(dtsiFlag, ",") {
			if p = strings.TrimSpace(p); p != "" {
				seeds = append(seeds, p)
			}
		}
	}
	rec, err := buildSocRecord(c.zephyr, name, seeds)
	if err != nil {
		return err
	}
	rec.Provenance = prov
	path := socPath(c.catalog, name)
	if err := writeRecord(path, rec, c.force); err != nil {
		return err
	}
	fmt.Printf("SOURCED soc %s → %s (%d dtsi, %d compatibles, %d power state(s), %d board(s))\n",
		name, path, len(rec.DtsiFiles), len(rec.Compatibles), len(rec.PowerStates), len(rec.Boards))
	return nil
}

// cmdVerify RE-EXTRACTS every catalog record through the same builders
// `add` uses and diffs the full content, field by field. A verify that
// only checked the SHA string and path existence passed every content
// falsification (proven by refutation, 2026-08-26) — that check is dead.
// Exit 0 now means: re-running the extraction reproduces every record.
func cmdVerify(args []string) error {
	c, err := parseCommon(flag.NewFlagSet("verify", flag.ExitOnError), args)
	if err != nil {
		return err
	}
	sha, err := ZephyrSHA(c.zephyr)
	if err != nil {
		return err
	}
	var failures []string
	checked := 0

	report := func(record string, recSHA string, diff []string) {
		if recSHA != sha {
			failures = append(failures, fmt.Sprintf("%s: extracted at %.12s, tree is at %.12s — re-extract", record, recSHA, sha))
		}
		for _, d := range diff {
			failures = append(failures, fmt.Sprintf("%s: %s", record, d))
		}
	}

	// Filename IS identity: a truthful record under a lying filename
	// misleads everything that selects by name (refuted 2026-08-26).
	checkName := func(f, want string) {
		if filepath.Base(f) != filepath.Base(want) {
			failures = append(failures, fmt.Sprintf("%s: filename does not match record identity (want %s)", f, filepath.Base(want)))
		}
	}

	comps, _ := filepath.Glob(filepath.Join(c.catalog, "components", "*.yaml"))
	for _, f := range comps {
		var stored ComponentRecord
		if err := readYAML(f, &stored); err != nil {
			failures = append(failures, fmt.Sprintf("%s: unreadable: %v", f, err))
			continue
		}
		checked++
		checkName(f, componentPath(c.catalog, stored.Compatible))
		rebuilt, err := buildComponentRecord(c.zephyr, stored.Compatible)
		if err != nil {
			failures = append(failures, fmt.Sprintf("%s: rebuild failed: %v", f, err))
			continue
		}
		diff, err := recordDiff(&stored, rebuilt)
		if err != nil {
			return err
		}
		report(f, stored.Provenance.ZephyrSHA, diff)
	}
	socs, _ := filepath.Glob(filepath.Join(c.catalog, "socs", "*.yaml"))
	for _, f := range socs {
		var stored SocRecord
		if err := readYAML(f, &stored); err != nil {
			failures = append(failures, fmt.Sprintf("%s: unreadable: %v", f, err))
			continue
		}
		checked++
		checkName(f, socPath(c.catalog, stored.Name))
		var seeds []string // auto-discovery unless the record was manual
		if stored.DtsiDiscovery == "manual" {
			seeds = stored.DtsiSeeds
		}
		rebuilt, err := buildSocRecord(c.zephyr, stored.Name, seeds)
		if err != nil {
			failures = append(failures, fmt.Sprintf("%s: rebuild failed: %v", f, err))
			continue
		}
		diff, err := recordDiff(&stored, rebuilt)
		if err != nil {
			return err
		}
		report(f, stored.Provenance.ZephyrSHA, diff)
	}

	if checked == 0 {
		return fmt.Errorf("verify selected ZERO records under %s — an empty scope is not a pass", c.catalog)
	}
	if len(failures) > 0 {
		for _, f := range failures {
			fmt.Fprintln(os.Stderr, "DRIFT:", f)
		}
		return fmt.Errorf("%d failure(s) across %d record(s)", len(failures), checked)
	}
	fmt.Printf("verify OK: %d record(s) reproduced from zephyr @ %.12s\n", checked, sha)
	return nil
}

func readYAML(path string, out any) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return yaml.Unmarshal(raw, out)
}
