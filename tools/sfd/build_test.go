package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Refuter finding #1: verify checked only SHA string + path existence, so
// every content falsification passed green — including invented
// compatibles, tampered power-state numbers, hand-set depth D3 and a
// part_numbers entry (forbidden before P4). Verify must re-extract and
// diff. These tests pin that contract at the function level.

func TestRecordDiffCatchesComponentTamper(t *testing.T) {
	rebuilt, err := buildComponentRecord(fixture, "test,fakesensor")
	if err != nil {
		t.Fatal(err)
	}
	tampered := *rebuilt
	tampered.Depth = "D3"                        // unearned promotion
	tampered.PartNumbers = []string{"ACME-9000"} // forbidden before P4
	tampered.Buses = []string{"can"}             // falsified bus
	diff, err := recordDiff(&tampered, rebuilt)
	if err != nil {
		t.Fatal(err)
	}
	if len(diff) == 0 {
		t.Fatal("tampered record produced no diff — verify cannot fail on content")
	}
	joined := strings.Join(diff, "\n")
	for _, needle := range []string{"D3", "ACME-9000", "can"} {
		if !strings.Contains(joined, needle) {
			t.Errorf("diff does not name the falsified value %q:\n%s", needle, joined)
		}
	}
}

// Round-2 refuter finding: a line-multiset diff is blind to PERMUTATIONS.
// Swapping which power state owns which numbers, or which binding owns
// which bus, changes no line — only their arrangement — and verified
// green. The comparison must be positional, full serialized content.
func TestRecordDiffCatchesPermutation(t *testing.T) {
	rebuilt, err := buildSocRecord(fixture, "testsoc1", nil)
	if err != nil {
		t.Fatal(err)
	}
	// Two states so a name swap is a pure permutation of existing lines.
	rebuilt.PowerStates = []PowerState{
		{Name: "standby", MinResidencyUS: 200, ExitLatencyUS: 60},
		{Name: "soft-off", MinResidencyUS: 2000, ExitLatencyUS: 212},
	}
	tampered := *rebuilt
	tampered.PowerStates = []PowerState{
		{Name: "soft-off", MinResidencyUS: 200, ExitLatencyUS: 60},
		{Name: "standby", MinResidencyUS: 2000, ExitLatencyUS: 212},
	}
	diff, err := recordDiff(&tampered, rebuilt)
	if err != nil {
		t.Fatal(err)
	}
	if len(diff) == 0 {
		t.Fatal("power-state name swap verified green — permutation blindness")
	}
}

func TestRecordDiffCatchesBusSwap(t *testing.T) {
	rebuilt, err := buildComponentRecord(fixture, "test,fakesensor")
	if err != nil {
		t.Fatal(err)
	}
	rebuilt.Bindings = []BindingRef{
		{Path: "dts/bindings/sensor/a-i2c.yaml", OnBus: "i2c", Class: "sensor"},
		{Path: "dts/bindings/sensor/a-spi.yaml", OnBus: "spi", Class: "sensor"},
	}
	tampered := *rebuilt
	tampered.Bindings = []BindingRef{
		{Path: "dts/bindings/sensor/a-i2c.yaml", OnBus: "spi", Class: "sensor"},
		{Path: "dts/bindings/sensor/a-spi.yaml", OnBus: "i2c", Class: "sensor"},
	}
	diff, err := recordDiff(&tampered, rebuilt)
	if err != nil {
		t.Fatal(err)
	}
	if len(diff) == 0 {
		t.Fatal("on_bus swap between bindings verified green — permutation blindness")
	}
}

func TestRecordDiffCleanOnTruth(t *testing.T) {
	a, err := buildComponentRecord(fixture, "test,fakesensor")
	if err != nil {
		t.Fatal(err)
	}
	b, err := buildComponentRecord(fixture, "test,fakesensor")
	if err != nil {
		t.Fatal(err)
	}
	diff, err := recordDiff(a, b)
	if err != nil {
		t.Fatal(err)
	}
	if len(diff) != 0 {
		t.Fatalf("identical records must not drift: %v", diff)
	}
}

func TestRecordDiffCatchesSocTamper(t *testing.T) {
	rebuilt, err := buildSocRecord(fixture, "testsoc1", nil)
	if err != nil {
		t.Fatal(err)
	}
	tampered := *rebuilt
	tampered.Compatibles = append([]string{"acme,fusion-reactor"}, tampered.Compatibles...)
	tampered.PowerStates = []PowerState{{Name: "suspend-to-idle", MinResidencyUS: 999999, ExitLatencyUS: 1}}
	diff, err := recordDiff(&tampered, rebuilt)
	if err != nil {
		t.Fatal(err)
	}
	joined := strings.Join(diff, "\n")
	if !strings.Contains(joined, "acme,fusion-reactor") || !strings.Contains(joined, "999999") {
		t.Fatalf("soc tamper not named in diff:\n%s", joined)
	}
}

// Round-3 refuter finding: readYAML accepted unknown keys, so a record
// could carry un-gated assertions ("verified_by: mateo",
// "safe_for_pc0: true") that verify never checks — the exact failure mode
// the provenance thesis exists to prevent.
func TestReadYAMLRejectsUnknownKeys(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "x.yaml")
	content := "schema: sfd.component/v0\ncompatible: a,b\nverified_by: mateo\n"
	if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	var rec ComponentRecord
	if err := readYAML(p, &rec); err == nil {
		t.Fatal("unknown key 'verified_by' accepted — un-gated assertions can ride inside a record")
	}
}

// Round-3 refuter finding: the catalog glob was non-recursive *.yaml only —
// a .yml file or a subdirectory was silently out of scope while verify
// reported OK. A stray in the catalog is a failure that names the file.
func TestCatalogScanFlagsStrays(t *testing.T) {
	dir := t.TempDir()
	for _, d := range []string{"components", "socs", filepath.Join("components", "sub")} {
		if err := os.MkdirAll(filepath.Join(dir, d), 0o755); err != nil {
			t.Fatal(err)
		}
	}
	write := func(rel string) {
		if err := os.WriteFile(filepath.Join(dir, rel), []byte("x: 1\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	write(filepath.Join("components", "good.yaml"))
	write(filepath.Join("components", "stray.yml"))            // wrong extension
	write(filepath.Join("components", "sub", "hidden.yaml"))   // out-of-scope subdir
	write(filepath.Join("socs", "notes.txt"))                  // stray file
	comps, socs, problems := catalogScan(dir)
	if len(comps) != 1 || len(socs) != 0 {
		t.Fatalf("scan: want 1 component, 0 socs; got %v / %v", comps, socs)
	}
	if len(problems) != 3 {
		t.Fatalf("want 3 named strays (stray.yml, sub/hidden.yaml, notes.txt), got %v", problems)
	}
}

// The builders are the single code path shared by add and verify — a
// build on the fixture must carry the values the extraction tests pin.
func TestBuildSocRecordShape(t *testing.T) {
	rec, err := buildSocRecord(fixture, "testsoc1", nil)
	if err != nil {
		t.Fatal(err)
	}
	if rec.DtsiDiscovery != "auto" {
		t.Errorf("discovery: want auto, got %q", rec.DtsiDiscovery)
	}
	if len(rec.DtsiSeeds) == 0 || len(rec.DtsiFiles) < len(rec.DtsiSeeds) {
		t.Errorf("closure must contain the seeds: seeds=%v files=%v", rec.DtsiSeeds, rec.DtsiFiles)
	}
	if len(rec.PartNumbers) != 0 {
		t.Errorf("part numbers must be empty at build time")
	}
}
