package main

// Record builders — the ONE code path that turns a Zephyr tree into a
// record. `add` writes what these return; `verify` re-runs them and diffs.
// A verify that does not re-extract is a check that cannot fail on content
// (proven by refutation, 2026-08-26).

import (
	"fmt"
	"os"
	"path/filepath"

	"strings"

	"gopkg.in/yaml.v3"
)

// buildComponentRecord extracts a component record, provenance excluded.
func buildComponentRecord(zephyr, compatible string) (*ComponentRecord, error) {
	bindings, err := FindBindings(zephyr, compatible)
	if err != nil {
		return nil, err
	}
	if len(bindings) == 0 {
		return nil, fmt.Errorf("no binding for %q in %s — this component is DRIVER-WORK, not SOURCED", compatible, zephyr)
	}
	drivers, err := FindDrivers(zephyr, compatible)
	if err != nil {
		return nil, err
	}
	exercisers, err := FindExercisers(zephyr, compatible, 20)
	if err != nil {
		return nil, err
	}
	depth := "D1"
	if len(drivers) > 0 {
		depth = "D2"
	}
	seen := map[string]bool{}
	var buses []string
	for _, b := range bindings {
		if b.OnBus != "" && !seen[b.OnBus] {
			seen[b.OnBus] = true
			buses = append(buses, b.OnBus)
		}
	}
	return &ComponentRecord{
		Schema:      "sfd.component/v0",
		Compatible:  compatible,
		Class:       bindings[0].Class,
		Buses:       buses,
		Bindings:    bindings,
		Drivers:     drivers,
		ExercisedBy: exercisers,
		Depth:       depth,
		PartNumbers: []string{},
	}, nil
}

// buildSocRecord extracts a SoC record, provenance excluded. dtsiSeeds nil
// means auto-discovery; non-nil is the --dtsi manual path, recorded as such
// so verify can rebuild the same way.
func buildSocRecord(zephyr, name string, dtsiSeeds []string) (*SocRecord, error) {
	decl, err := FindSoc(zephyr, name)
	if err != nil {
		return nil, err
	}
	boards, err := FindBoardsForSoc(zephyr, name)
	if err != nil {
		return nil, err
	}
	discovery := "auto"
	if dtsiSeeds == nil {
		dtsiSeeds, err = FindSocDtsi(zephyr, name, boards)
		if err != nil {
			return nil, err
		}
	} else {
		discovery = "manual"
		for _, f := range dtsiSeeds {
			if _, err := os.Stat(filepath.Join(zephyr, f)); err != nil {
				return nil, fmt.Errorf("--dtsi %s: %w", f, err)
			}
		}
	}
	// Record the full include closure, not just the seeds: it is what was
	// actually read, and verify then catches drift in any of it.
	dtsi := expandIncludes(zephyr, dtsiSeeds)
	compatibles, states, err := DtsiInventory(zephyr, dtsi)
	if err != nil {
		return nil, err
	}
	return &SocRecord{
		Schema:        "sfd.soc/v0",
		Name:          name,
		Family:        decl.Family,
		Series:        decl.Series,
		SocYML:        decl.SocYML,
		DtsiDiscovery: discovery,
		DtsiSeeds:     dtsiSeeds,
		DtsiFiles:     dtsi,
		Compatibles:   compatibles,
		PowerStates:   states,
		Boards:        boards,
		Depth:         "D1",
		PartNumbers:   []string{},
	}, nil
}

// recordDiff compares a stored record against a freshly rebuilt one,
// provenance excluded (the SHA is checked separately). It returns one line
// per difference; empty means the stored record tells the truth. YAML
// serialization is the comparison domain, so EVERY field participates —
// a check that skips a field is a check that cannot fail on it.
func recordDiff(stored, rebuilt any) ([]string, error) {
	normalize := func(v any) ([]string, error) {
		switch r := v.(type) {
		case *ComponentRecord:
			c := *r
			c.Provenance = Provenance{}
			v = &c
		case *SocRecord:
			s := *r
			s.Provenance = Provenance{}
			v = &s
		}
		raw, err := yaml.Marshal(v)
		if err != nil {
			return nil, err
		}
		return strings.Split(strings.TrimRight(string(raw), "\n"), "\n"), nil
	}
	a, err := normalize(stored)
	if err != nil {
		return nil, err
	}
	b, err := normalize(rebuilt)
	if err != nil {
		return nil, err
	}
	// The VERDICT is positional equality of the full serialization. A
	// line-multiset comparison verified permutations green (power-state
	// names swapped onto other states' numbers, on_bus values traded
	// between bindings) — refuted twice, 2026-08-26.
	if strings.Join(a, "\n") == strings.Join(b, "\n") {
		return nil, nil
	}
	// Reporting: name the multiset differences first (most readable)…
	inB := map[string]int{}
	for _, l := range b {
		inB[l]++
	}
	inA := map[string]int{}
	for _, l := range a {
		inA[l]++
	}
	var diff []string
	for _, l := range a {
		if inB[l] == 0 {
			diff = append(diff, "stored-only:  "+l)
		} else {
			inB[l]--
		}
	}
	for _, l := range b {
		if inA[l] == 0 {
			diff = append(diff, "rebuilt-only: "+l)
		} else {
			inA[l]--
		}
	}
	// …and when the multisets agree (a pure permutation), name the first
	// positions where the serializations diverge.
	if len(diff) == 0 {
		for i := 0; i < len(a) || i < len(b); i++ {
			la, lb := "", ""
			if i < len(a) {
				la = a[i]
			}
			if i < len(b) {
				lb = b[i]
			}
			if la != lb {
				diff = append(diff, fmt.Sprintf("line %d reordered: stored %q, rebuilt %q", i+1, strings.TrimSpace(la), strings.TrimSpace(lb)))
				if len(diff) >= 8 {
					diff = append(diff, "… (more reordered lines elided)")
					break
				}
			}
		}
	}
	return diff, nil
}
