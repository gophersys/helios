//go:build lifecycle

package configuration_test

import (
	"context"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// configuration is a parse-time leaf that owns NO closeable OS resource: New is pure, the Parser
// is immutable and stateless after construction, and the Document it yields is a frozen, read-only
// IR. There is therefore no Close to make idempotent and no external resource to reap, so the
// testing.AssertLifecycle / LifecycleProbe driver (which exists for handles that own
// containers/clusters/fds, ADR-0020 dimension (c)) does not apply. The leaf-library FORM of the
// lifecycle invariant — the analog of "double-close is a no-op" and "CountOwned()==0" — is
// IMMUTABILITY AND REPEAT-USE PURITY: a frozen Document re-read any number of times yields the
// same values and the Parser re-Parsed repeatedly is referentially transparent, mutating no
// shared state. A regression that mutated the IR on read, or made Parse stateful, would be this
// leaf's equivalent of an orphaned resource. goleak.VerifyNone asserts the orphan-goroutine half.

// TestLifecycle_DocumentReadIsRepeatableAndPure is the construct→use→re-use→teardown form: build a
// Document once, read it many times, and assert every read is identical and side-effect-free (the
// "double-close is a no-op" analog — a second read changes nothing).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; a parallel sibling would perturb the orphan-goroutine assertion, so the lifecycle probe runs serially.
func TestLifecycle_DocumentReadIsRepeatableAndPure(t *testing.T) {
	defer goleak.VerifyNone(t) // the orphan-goroutine half of the lifecycle assertion

	src := configurationtest.Source{Files: map[string][]byte{
		"app.json": []byte(`{"engine":{"models":[{"name":"a"},{"name":"b"}]},"port":8080,"debug":true}`),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, diags, perr := p.Parse(context.Background(), "app.json")
	if perr != nil {
		t.Fatalf("Parse I/O err = %v", perr)
	}
	if diags.HasError() {
		t.Fatalf("clean source produced errors: %v", diags.All())
	}

	read := func() (string, int64, bool) {
		nameV, _ := doc.Lookup("engine.models[1].name")
		name, _ := nameV.String()
		portV, _ := doc.Lookup("port")
		port, _ := portV.Int()
		debugV, _ := doc.Lookup("debug")
		debug, _ := debugV.Bool()
		return name, port, debug
	}

	// First "use".
	wantName, wantPort, wantDebug := read()
	if wantName != "b" || wantPort != 8080 || !wantDebug {
		t.Fatalf("first read wrong: (%q,%d,%v)", wantName, wantPort, wantDebug)
	}
	// Re-use many times — every read must be identical (frozen IR; no mutation on read).
	for i := range 64 {
		gotName, gotPort, gotDebug := read()
		if gotName != wantName || gotPort != wantPort || gotDebug != wantDebug {
			t.Fatalf("read %d drifted: (%q,%d,%v) != (%q,%d,%v)",
				i, gotName, gotPort, gotDebug, wantName, wantPort, wantDebug)
		}
	}
}

// TestLifecycle_ParseIsReferentiallyTransparent is the repeated-construction form: the same Parser
// re-Parsing the same source repeatedly yields structurally identical Documents and never
// accumulates state (the "no orphan" analog — Parse leaves nothing behind between calls).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine assertion.
func TestLifecycle_ParseIsReferentiallyTransparent(t *testing.T) {
	defer goleak.VerifyNone(t)

	src := configurationtest.Source{Files: map[string][]byte{"d.env": []byte("A=1\nB=two\nC=true\n")}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatEnv}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}

	var firstA int64
	for i := range 8 {
		doc, diags, perr := p.Parse(context.Background(), "d.env")
		if perr != nil {
			t.Fatalf("Parse %d I/O err = %v", i, perr)
		}
		if diags.HasError() {
			t.Fatalf("Parse %d produced errors: %v", i, diags.All())
		}
		av, _ := doc.Lookup("A")
		a, d := av.Int()
		if d != nil {
			t.Fatalf("Parse %d A Int() diagnostic = %v", i, d)
		}
		bv, _ := doc.Lookup("B")
		if s, _ := bv.String(); s != "two" {
			t.Fatalf("Parse %d B = %q, want two", i, s)
		}
		if i == 0 {
			firstA = a
		} else if a != firstA {
			t.Fatalf("Parse %d A = %d drifted from first %d (Parser accumulated state)", i, a, firstA)
		}
	}
}
