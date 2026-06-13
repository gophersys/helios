package dependencies_test

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// engineDeps mirrors §5 Site 2: a kernel library NARROWS the universal Set into
// its own Deps holding only the ports it touches (time + entropy).
type engineDeps struct {
	Clock  dependencies.Clock
	Random dependencies.RandomSource
}

// engineNew mirrors §5 Site 2: New stays PURE — it validates the narrowed ports,
// binds no real adapter, reads no clock/env, and wraps MissingPortError with %w.
func engineNew(deps engineDeps) (*engine, error) {
	if deps.Clock == nil {
		return nil, fmt.Errorf("engine: %w", &dependencies.MissingPortError{Port: "Clock"})
	}
	if deps.Random == nil {
		return nil, fmt.Errorf("engine: %w", &dependencies.MissingPortError{Port: "RandomSource"})
	}
	return &engine{clock: deps.Clock, random: deps.Random}, nil
}

type engine struct {
	clock  dependencies.Clock
	random dependencies.RandomSource
}

// runWithTimeout uses the injected Clock.After so the timeout is drivable by a
// fake clock's Advance — the determinism the port exists to provide (§5 Site 3).
// It returns the timer channel via started so a test can deterministically wait
// for the timer to be registered before advancing the clock.
func (e *engine) runWithTimeout(ctx context.Context, work <-chan struct{}, d time.Duration, started chan<- struct{}) (timedOut bool) {
	timer := e.clock.After(ctx, d)
	close(started) // After has registered the deadline; the test may now Advance.
	select {
	case <-work:
		return false
	case <-timer:
		return true
	}
}

// §5 Site 3: deterministic by construction — drive the timeout via Advance, no
// real waiting.
func TestEngineTimeoutDeterministic(t *testing.T) {
	set, clock, random, _ := dependenciestest.Fakes()
	e, err := engineNew(engineDeps{Clock: set.Clock, Random: set.Random})
	if err != nil {
		t.Fatalf("engineNew: %v", err)
	}
	_ = random

	work := make(chan struct{}) // never delivered: force the timeout path
	done := make(chan bool, 1)
	started := make(chan struct{})
	go func() { done <- e.runWithTimeout(context.Background(), work, 30*time.Second, started) }()

	<-started                       // the After deadline is registered
	clock.Advance(30 * time.Second) // cross the deadline without real waiting
	select {
	case got := <-done:
		if !got {
			t.Fatal("expected the engine to time out")
		}
	case <-time.After(time.Second):
		t.Fatal("engine did not observe the fake-clock timeout")
	}
}

// §5 Site 1/2: a narrowing constructor surfaces a missing port structurally via
// *MissingPortError (errors.As), not as a nil panic at first use.
func TestEngineMissingPortStructural(t *testing.T) {
	_, err := engineNew(engineDeps{ /* Clock nil */ Random: dependenciestest.NewRandom([32]byte{})})
	if err == nil {
		t.Fatal("expected a missing-port error")
	}
	var missing *dependencies.MissingPortError
	if !errors.As(err, &missing) {
		t.Fatalf("error not recoverable via errors.As: %T", err)
	}
	if missing.Port != "Clock" {
		t.Fatalf("Port = %q, want Clock", missing.Port)
	}
}

// §5 Site 1: a composition root NARROWS the resolved Set; Resolve fills any unset
// port with its real adapter and the narrowed Deps validates.
func TestCompositionRootNarrowing(t *testing.T) {
	base := dependencies.Resolve(dependencies.Set{})
	e, err := engineNew(engineDeps{Clock: base.Clock, Random: base.Random})
	if err != nil {
		t.Fatalf("composition-root wiring failed: %v", err)
	}
	if e.clock == nil || e.random == nil {
		t.Fatal("narrowed Deps did not carry the resolved ports")
	}
}
