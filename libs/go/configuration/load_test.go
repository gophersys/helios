//go:build load

package configuration_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500 in-process;
// ADR-0020 dimension (e) threshold).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentParseAndReadRaceClean fans out N goroutines that each Parse the same Source
// and read the resulting Document concurrently, while another cohort reads a SHARED pre-parsed
// Document. The contract documents that the Parser is "stateless and safe for concurrent use" and
// the Document is "immutable after Parse, safe to share across goroutines"; this proves it under
// -race at fan-out, and goleak asserts the goroutine high-water returns to baseline (0 leaked)
// afterward (ADR-0020 dimension (e)).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine high-water assertion.
func TestLoad_ConcurrentParseAndReadRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	src := configurationtest.Source{Files: map[string][]byte{
		"svc.json": []byte(`{"engine":{"models":[{"name":"a"},{"name":"b"}]},"port":8080,"flags":{"debug":true}}`),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}

	// A shared, frozen Document read concurrently by half the fan-out.
	shared, _, perr := p.Parse(context.Background(), "svc.json")
	if perr != nil {
		t.Fatalf("seed Parse err = %v", perr)
	}

	var wg sync.WaitGroup
	wg.Add(n)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			if i%2 == 0 {
				parseAndReadWorker(t, p, i)
			} else {
				readSharedWorker(t, shared, i)
			}
		}(i)
	}
	wg.Wait()

	// The shared Document is unchanged after N concurrent reads (no mutation under load).
	v, _ := shared.Lookup("engine.models[0].name")
	if s, _ := v.String(); s != "a" {
		t.Fatalf("shared Document mutated under load: engine.models[0].name = %q, want a", s)
	}
}

// parseAndReadWorker does an independent Parse on the shared stateless Parser and reads a nested
// leaf back — one fan-out worker (extracted to keep the load body under the complexity floor).
func parseAndReadWorker(t *testing.T, p configuration.Parser, i int) {
	t.Helper()
	doc, _, e := p.Parse(context.Background(), "svc.json")
	if e != nil {
		t.Errorf("worker %d Parse err = %v", i, e)
		return
	}
	v, ok := doc.Lookup("engine.models[1].name")
	if !ok {
		t.Errorf("worker %d lost engine.models[1].name", i)
		return
	}
	if s, _ := v.String(); s != "b" {
		t.Errorf("worker %d read %q, want b", i, s)
	}
}

// readSharedWorker reads two leaves of the SHARED frozen Document concurrently — one fan-out worker.
func readSharedWorker(t *testing.T, shared configuration.Document, i int) {
	t.Helper()
	pv, _ := shared.Lookup("port")
	if port, _ := pv.Int(); port != 8080 {
		t.Errorf("worker %d shared port = %d, want 8080", i, port)
	}
	dv, _ := shared.Lookup("flags.debug")
	if debug, _ := dv.Bool(); !debug {
		t.Errorf("worker %d shared flags.debug = false, want true", i)
	}
}

// TestLoad_ConcurrentMergeRaceClean fans out N concurrent Merge folds over the same pair of
// immutable base/overlay Documents. Merge must build fresh trees and never write the inputs, so N
// concurrent folds are race-clean and leave both inputs intact (ADR-0020 dimension (e)).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine high-water assertion.
func TestLoad_ConcurrentMergeRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	src := configurationtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"k":1,"only":"base","nested":{"a":1}}`),
		"overlay.json": []byte(`{"k":2,"nested":{"b":2}}`),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	base, _, berr := p.Parse(context.Background(), "base.json")
	if berr != nil {
		t.Fatalf("Parse(base) err = %v", berr)
	}
	overlay, _, oerr := p.Parse(context.Background(), "overlay.json")
	if oerr != nil {
		t.Fatalf("Parse(overlay) err = %v", oerr)
	}

	var wg sync.WaitGroup
	wg.Add(n)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			merged, _, e := p.Merge(context.Background(), base, overlay)
			if e != nil {
				t.Errorf("worker %d Merge err = %v", i, e)
				return
			}
			kv, _ := merged.Lookup("k")
			if k, _ := kv.Int(); k != 2 {
				t.Errorf("worker %d merged k = %d, want 2 (overlay wins)", i, k)
			}
			if _, ok := merged.Lookup("only"); !ok {
				t.Errorf("worker %d lost base-only key under fan-out", i)
			}
		}(i)
	}
	wg.Wait()

	// Inputs unmutated after N concurrent merges.
	bv, _ := base.Lookup("k")
	if k, _ := bv.Int(); k != 1 {
		t.Fatalf("Merge mutated base under load: k = %d, want 1", k)
	}
	ov, _ := overlay.Lookup("k")
	if k, _ := ov.Int(); k != 2 {
		t.Fatalf("Merge mutated overlay under load: k = %d, want 2", k)
	}
}
