package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
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
	bindings, err := FindBindings(c.zephyr, compatible)
	if err != nil {
		return err
	}
	if len(bindings) == 0 {
		return fmt.Errorf("no binding for %q in %s — this component is DRIVER-WORK, not SOURCED", compatible, c.zephyr)
	}
	drivers, err := FindDrivers(c.zephyr, compatible)
	if err != nil {
		return err
	}
	exercisers, err := FindExercisers(c.zephyr, compatible, 20)
	if err != nil {
		return err
	}

	depth := "D1"
	if len(drivers) > 0 {
		depth = "D2"
	}
	buses := map[string]bool{}
	var busList []string
	for _, b := range bindings {
		if b.OnBus != "" && !buses[b.OnBus] {
			buses[b.OnBus] = true
			busList = append(busList, b.OnBus)
		}
	}
	rec := ComponentRecord{
		Schema:      "sfd.component/v0",
		Compatible:  compatible,
		Class:       bindings[0].Class,
		Buses:       busList,
		Bindings:    bindings,
		Drivers:     drivers,
		ExercisedBy: exercisers,
		Depth:       depth,
		PartNumbers: []string{},
		Provenance:  prov,
	}
	path := componentPath(c.catalog, compatible)
	if err := writeRecord(path, &rec, c.force); err != nil {
		return err
	}
	fmt.Printf("SOURCED %s → %s (depth %s, %d binding(s), %d driver dir(s), %d exerciser(s))\n",
		compatible, path, depth, len(bindings), len(drivers), len(exercisers))
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
	decl, err := FindSoc(c.zephyr, name)
	if err != nil {
		return err
	}
	boards, err := FindBoardsForSoc(c.zephyr, name)
	if err != nil {
		return err
	}
	var dtsi []string
	if dtsiFlag != "" {
		dtsi = filepath.SplitList(dtsiFlag)
		if len(dtsi) == 1 {
			dtsi = splitComma(dtsiFlag)
		}
		for _, f := range dtsi {
			if _, err := os.Stat(filepath.Join(c.zephyr, f)); err != nil {
				return fmt.Errorf("--dtsi %s: %w", f, err)
			}
		}
	} else {
		dtsi, err = FindSocDtsi(c.zephyr, name, boards)
		if err != nil {
			return err
		}
	}
	// Record the full include closure, not just the seeds: it is what was
	// actually read, and verify then catches drift in any of it.
	dtsi = expandIncludes(c.zephyr, dtsi)
	compatibles, states, err := DtsiInventory(c.zephyr, dtsi)
	if err != nil {
		return err
	}
	rec := SocRecord{
		Schema:      "sfd.soc/v0",
		Name:        name,
		Family:      decl.Family,
		Series:      decl.Series,
		SocYML:      decl.SocYML,
		DtsiFiles:   dtsi,
		Compatibles: compatibles,
		PowerStates: states,
		Boards:      boards,
		Depth:       "D1",
		PartNumbers: []string{},
		Provenance:  prov,
	}
	path := socPath(c.catalog, name)
	if err := writeRecord(path, &rec, c.force); err != nil {
		return err
	}
	fmt.Printf("SOURCED soc %s → %s (%d dtsi, %d compatibles, %d power state(s), %d board(s))\n",
		name, path, len(dtsi), len(compatibles), len(states), len(boards))
	return nil
}

func splitComma(s string) []string {
	var out []string
	for _, p := range filepath.SplitList(s) {
		out = append(out, p)
	}
	if len(out) == 1 {
		out = nil
		for _, p := range splitOn(s, ',') {
			if p != "" {
				out = append(out, p)
			}
		}
	}
	return out
}

func splitOn(s string, sep rune) []string {
	var out []string
	cur := ""
	for _, r := range s {
		if r == sep {
			out = append(out, cur)
			cur = ""
			continue
		}
		cur += string(r)
	}
	return append(out, cur)
}

// cmdVerify re-checks every catalog record against the tree. Any drift is
// red and named. Exit 0 means: every record matches the pinned tree.
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

	checkPaths := func(record string, recSHA string, paths []string) {
		if recSHA != sha {
			failures = append(failures, fmt.Sprintf("%s: extracted at %.12s, tree is at %.12s — re-extract", record, recSHA, sha))
		}
		for _, p := range paths {
			if _, err := os.Stat(filepath.Join(c.zephyr, p)); err != nil {
				failures = append(failures, fmt.Sprintf("%s: cited path missing: %s", record, p))
			}
		}
	}

	comps, _ := filepath.Glob(filepath.Join(c.catalog, "components", "*.yaml"))
	for _, f := range comps {
		var rec ComponentRecord
		if err := readYAML(f, &rec); err != nil {
			failures = append(failures, fmt.Sprintf("%s: unreadable: %v", f, err))
			continue
		}
		checked++
		var paths []string
		for _, b := range rec.Bindings {
			paths = append(paths, b.Path)
		}
		paths = append(paths, rec.Drivers...)
		checkPaths(f, rec.Provenance.ZephyrSHA, paths)
	}
	socs, _ := filepath.Glob(filepath.Join(c.catalog, "socs", "*.yaml"))
	for _, f := range socs {
		var rec SocRecord
		if err := readYAML(f, &rec); err != nil {
			failures = append(failures, fmt.Sprintf("%s: unreadable: %v", f, err))
			continue
		}
		checked++
		paths := append([]string{rec.SocYML}, rec.DtsiFiles...)
		checkPaths(f, rec.Provenance.ZephyrSHA, paths)
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
	fmt.Printf("verify OK: %d record(s) match zephyr @ %.12s\n", checked, sha)
	return nil
}

func readYAML(path string, out any) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return yaml.Unmarshal(raw, out)
}
