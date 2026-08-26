package main

import (
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
