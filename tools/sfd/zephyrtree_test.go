package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const fixture = "testdata/minizephyr"

func TestFindBindings(t *testing.T) {
	refs, err := FindBindings(fixture, "test,fakesensor")
	if err != nil {
		t.Fatal(err)
	}
	if len(refs) != 1 {
		t.Fatalf("want 1 binding, got %d: %+v", len(refs), refs)
	}
	b := refs[0]
	if b.OnBus != "i2c" {
		t.Errorf("on-bus: want i2c, got %q", b.OnBus)
	}
	if b.Class != "sensor" {
		t.Errorf("class: want sensor, got %q", b.Class)
	}
	if b.Path != filepath.Join("dts", "bindings", "sensor", "test,fakesensor.yaml") {
		t.Errorf("unexpected path %q", b.Path)
	}
}

// The refusal path IS the process: a compatible with no upstream binding
// must yield zero results, which component-add turns into a hard error.
func TestFindBindingsRefusesUnknown(t *testing.T) {
	refs, err := FindBindings(fixture, "nosuch,component")
	if err != nil {
		t.Fatal(err)
	}
	if len(refs) != 0 {
		t.Fatalf("want 0 bindings for unknown compatible, got %d", len(refs))
	}
}

// The bme280 lesson: most device bindings carry no literal `on-bus:` —
// the bus arrives via `include: [i2c-device.yaml]`. Bus derivation must
// resolve binding includes or buses report empty.
func TestFindBindingsResolvesBusFromInclude(t *testing.T) {
	refs, err := FindBindings(fixture, "test,incsensor")
	if err != nil {
		t.Fatal(err)
	}
	if len(refs) != 1 {
		t.Fatalf("want 1 binding, got %d", len(refs))
	}
	if refs[0].OnBus != "i2c" {
		t.Fatalf("on-bus via include: want i2c, got %q", refs[0].OnBus)
	}
}

func TestFindDrivers(t *testing.T) {
	dirs, err := FindDrivers(fixture, "test,fakesensor")
	if err != nil {
		t.Fatal(err)
	}
	want := filepath.Join("drivers", "sensor", "fakesensor")
	if len(dirs) != 1 || dirs[0] != want {
		t.Fatalf("want [%s], got %v", want, dirs)
	}
}

func TestFindExercisers(t *testing.T) {
	hits, err := FindExercisers(fixture, "test,fakesensor", 20)
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 1 || hits[0] != filepath.Join("samples", "fake", "app.overlay") {
		t.Fatalf("want the sample overlay, got %v", hits)
	}
}

func TestFindSoc(t *testing.T) {
	decl, err := FindSoc(fixture, "testsoc1")
	if err != nil {
		t.Fatal(err)
	}
	if decl.Family != "testfam" || decl.Series != "tseries" {
		t.Errorf("family/series: got %q/%q", decl.Family, decl.Series)
	}
	if decl.SocYML != filepath.Join("soc", "testvendor", "testfam", "soc.yml") {
		t.Errorf("soc_yml path: got %q", decl.SocYML)
	}
}

func TestFindSocUnknownFails(t *testing.T) {
	if _, err := FindSoc(fixture, "ghostsoc"); err == nil {
		t.Fatal("want error for undeclared soc, got nil")
	}
}

func TestFindBoardsForSoc(t *testing.T) {
	boards, err := FindBoardsForSoc(fixture, "testsoc1")
	if err != nil {
		t.Fatal(err)
	}
	if len(boards) != 1 || boards[0] != filepath.Join("boards", "testvendor", "testboard") {
		t.Fatalf("got %v", boards)
	}
}

func TestFindSocDtsi(t *testing.T) {
	boards, _ := FindBoardsForSoc(fixture, "testsoc1")
	dtsi, err := FindSocDtsi(fixture, "testsoc1", boards)
	if err != nil {
		t.Fatal(err)
	}
	if len(dtsi) != 1 || dtsi[0] != filepath.Join("dts", "arm", "testvendor", "testsoc1.dtsi") {
		t.Fatalf("got %v", dtsi)
	}
}

// Refuter finding: `soc add esp32` swallowed esp32c2/c3/c6/s2/s3 — 75 dtsi
// across five chips and two ISAs, ten contradictory power states — because
// discovery was substring-based. A SoC name must match a dtsi basename
// exactly or at a separator boundary, never as a bare prefix.
func TestFindSocDtsiRejectsPrefixCollision(t *testing.T) {
	dtsi, err := FindSocDtsi(fixture, "testsoc1", nil)
	if err != nil {
		t.Fatal(err)
	}
	for _, f := range dtsi {
		if strings.Contains(f, "testsoc12") {
			t.Fatalf("testsoc1 discovery swallowed testsoc12's dtsi: %v", dtsi)
		}
	}
	if len(dtsi) == 0 {
		t.Fatal("discovery lost the genuine testsoc1.dtsi")
	}
}

// Refuter finding: exercised_by used bare substring match — 81 compatibles
// in the real tree would inherit evidence from a longer sibling
// (aosong,dht ← aosong,dht20). Evidence must match the exact quoted
// devicetree string.
func TestFindExercisersExactMatchOnly(t *testing.T) {
	hits, err := FindExercisers(fixture, "test,fakesensor", 20)
	if err != nil {
		t.Fatal(err)
	}
	for _, h := range hits {
		if strings.Contains(h, "fake2") {
			t.Fatalf("substring false positive: fakesensor credited with fakesensor2's overlay: %v", hits)
		}
	}
	if len(hits) != 1 {
		t.Fatalf("want exactly the genuine overlay, got %v", hits)
	}
}

func TestFindSocDtsiFailsLoudlyOnNoHit(t *testing.T) {
	if _, err := FindSocDtsi(fixture, "ghostsoc", nil); err == nil {
		t.Fatal("want loud failure when no dtsi found, got nil (silent empty is forbidden)")
	}
}

// The RT1052 lesson: a SoC dtsi is often a thin wrapper whose peripherals
// live in an included family dtsi (nxp_rt1050.dtsi -> nxp_rt10xx.dtsi,
// 1 vs 137 compatibles). Inventory MUST resolve the include closure, or the
// record silently lies.
func TestDtsiInventoryFollowsIncludes(t *testing.T) {
	compat, _, err := DtsiInventory(fixture,
		[]string{filepath.Join("dts", "arm", "testvendor", "testsoc1.dtsi")})
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, c := range compat {
		if c == "testvendor,spi" { // declared ONLY in the included family dtsi
			found = true
		}
	}
	if !found {
		t.Fatalf("inventory missed testvendor,spi from the included family dtsi; got %v", compat)
	}
}

func TestDtsiInventory(t *testing.T) {
	compat, states, err := DtsiInventory(fixture,
		[]string{filepath.Join("dts", "arm", "testvendor", "testsoc1.dtsi")})
	if err != nil {
		t.Fatal(err)
	}
	wantCompat := map[string]bool{
		"arm,cortex-m4": true, "zephyr,power-state": true,
		"testvendor,uart": true, "testvendor,i2c": true, "generic-i2c": true,
		"testvendor,spi": true, // via the include closure
	}
	if len(compat) != len(wantCompat) {
		t.Fatalf("compatibles: want %d, got %d: %v", len(wantCompat), len(compat), compat)
	}
	for _, c := range compat {
		if !wantCompat[c] {
			t.Errorf("unexpected compatible %q", c)
		}
	}
	if len(states) != 1 {
		t.Fatalf("want 1 power state, got %d: %+v", len(states), states)
	}
	s := states[0]
	if s.Name != "suspend-to-idle" || s.MinResidencyUS != 5000 || s.ExitLatencyUS != 120 {
		t.Errorf("power state mismatch: %+v", s)
	}
}

// Refuter finding: unparseable YAML was silently skipped. A skipped
// binding turns into "no binding → DRIVER-WORK" — the process's hardest
// refusal fired on a parser miss. FAIL-NOT-SKIP: a file that cannot be
// read is an error that names the file.
func TestBrokenYAMLFailsLoudly(t *testing.T) {
	broken := "testdata/broken"
	if _, err := FindBindings(broken, "any,thing"); err == nil ||
		!strings.Contains(err.Error(), "unparseable") || !strings.Contains(err.Error(), "bad.yaml") {
		t.Errorf("FindBindings: want unparseable error naming bad.yaml, got %v", err)
	}
	if _, err := FindSoc(broken, "anysoc"); err == nil ||
		!strings.Contains(err.Error(), "unparseable") || !strings.Contains(err.Error(), "soc.yml") {
		t.Errorf("FindSoc: want unparseable error naming soc.yml, got %v", err)
	}
	if _, err := FindBoardsForSoc(broken, "anysoc"); err == nil ||
		!strings.Contains(err.Error(), "unparseable") || !strings.Contains(err.Error(), "board.yml") {
		t.Errorf("FindBoardsForSoc: want unparseable error naming board.yml, got %v", err)
	}
}

func TestZephyrSHARefusesNonGit(t *testing.T) {
	if _, err := ZephyrSHA(fixture); err == nil {
		t.Fatal("want error for a non-git tree (provenance is mandatory), got nil")
	}
}

func TestWriteRecordRefusesOverwrite(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "x.yaml")
	if err := writeRecord(p, map[string]string{"a": "1"}, false); err != nil {
		t.Fatal(err)
	}
	if err := writeRecord(p, map[string]string{"a": "2"}, false); err == nil {
		t.Fatal("want refusal to overwrite without --force, got nil")
	}
	if err := writeRecord(p, map[string]string{"a": "2"}, true); err != nil {
		t.Fatalf("--force should overwrite: %v", err)
	}
	raw, _ := os.ReadFile(p)
	if string(raw) != "a: \"2\"\n" {
		t.Errorf("unexpected content after force: %q", raw)
	}
}
