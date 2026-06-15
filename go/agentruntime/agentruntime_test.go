package agentruntime_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/errors"
)

// TestNew_ValidatesInvariants proves New is the PURE spine guard: a missing AgentID or any nil port
// yields a typed *ConfigError (KindInvalid), and a fully-wired Deps constructs a non-nil Runtime.
func TestNew_ValidatesInvariants(t *testing.T) {
	t.Parallel()
	good := agentruntime.Deps{
		Sessions: agentruntimetest.NewSessions(t),
		Bus:      agentruntimetest.NewFakeBus(),
		Observer: agentruntimetest.NewFakeObserver(),
		Clock:    agentruntimetest.FixedClock{},
	}

	cases := []struct {
		name      string
		configure func() (agentruntime.Config, agentruntime.Deps)
		wantErr   bool
	}{
		{
			name:      "valid",
			configure: func() (agentruntime.Config, agentruntime.Deps) { return agentruntimetest.Config(nil), good },
			wantErr:   false,
		},
		{
			name: "missing agent id",
			configure: func() (agentruntime.Config, agentruntime.Deps) {
				return agentruntime.Config{}, good
			},
			wantErr: true,
		},
		{
			name: "nil sessions",
			configure: func() (agentruntime.Config, agentruntime.Deps) {
				dependencies := good
				dependencies.Sessions = nil
				return agentruntimetest.Config(nil), dependencies
			},
			wantErr: true,
		},
		{
			name: "nil bus",
			configure: func() (agentruntime.Config, agentruntime.Deps) {
				dependencies := good
				dependencies.Bus = nil
				return agentruntimetest.Config(nil), dependencies
			},
			wantErr: true,
		},
		{
			name: "nil observer",
			configure: func() (agentruntime.Config, agentruntime.Deps) {
				dependencies := good
				dependencies.Observer = nil
				return agentruntimetest.Config(nil), dependencies
			},
			wantErr: true,
		},
		{
			name: "nil clock",
			configure: func() (agentruntime.Config, agentruntime.Deps) {
				dependencies := good
				dependencies.Clock = nil
				return agentruntimetest.Config(nil), dependencies
			},
			wantErr: true,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			configuration, dependencies := tc.configure()
			runtime, err := agentruntime.New(configuration, dependencies)
			if tc.wantErr {
				assertConfigError(t, err)
				if runtime != nil {
					t.Errorf("New returned a non-nil Runtime alongside an error")
				}
				return
			}
			if err != nil {
				t.Fatalf("New returned an unexpected error: %v", err)
			}
			if runtime == nil {
				t.Fatal("New returned a nil Runtime with no error")
			}
		})
	}
}

// assertConfigError proves the error is the typed *ConfigError AND carries KindInvalid — inspected by
// type, never by string (the errors contract).
func assertConfigError(t *testing.T, err error) {
	t.Helper()
	if err == nil {
		t.Fatal("expected a ConfigError, got nil")
	}
	if !errors.IsType[*agentruntime.ConfigError](err) {
		t.Errorf("error is not a *ConfigError: %v", err)
	}
	if got := errors.KindOf(err); got != errors.KindInvalid {
		t.Errorf("ConfigError Kind = %v, want %v", got, errors.KindInvalid)
	}
}

// TestControlVerb_String proves the verb token round-trip is stable (the wire vocabulary is part of
// the protocol; a renamed token would silently break a consumer).
func TestControlVerb_String(t *testing.T) {
	t.Parallel()
	cases := map[agentruntime.ControlVerb]string{
		agentruntime.VerbPrompt: "prompt",
		agentruntime.VerbSteer:  "steer",
		agentruntime.VerbAbort:  "abort",
		agentruntime.VerbStop:   "stop",
		agentruntime.VerbKill:   "kill",
	}
	for verb, want := range cases {
		if got := verb.String(); got != want {
			t.Errorf("ControlVerb(%d).String() = %q, want %q", verb, got, want)
		}
	}
}

// TestTerminationReason_IsGraceful proves the graceful/non-graceful split main() maps to an exit code.
func TestTerminationReason_IsGraceful(t *testing.T) {
	t.Parallel()
	graceful := []agentruntime.TerminationReason{
		agentruntime.TerminationSignal,
		agentruntime.TerminationControlStop,
		agentruntime.TerminationSessionEnd,
	}
	for _, reason := range graceful {
		if !reason.IsGraceful() {
			t.Errorf("%s should be graceful", reason)
		}
	}
	notGraceful := []agentruntime.TerminationReason{
		agentruntime.TerminationControlKill,
		agentruntime.TerminationFault,
	}
	for _, reason := range notGraceful {
		if reason.IsGraceful() {
			t.Errorf("%s should not be graceful", reason)
		}
	}
}

// TestSubjects_OneHome proves the subject grammar renders per-agent consistently (the natsbus adapter
// and every consumer cite these; a drift would split the wire).
func TestSubjects_OneHome(t *testing.T) {
	t.Parallel()
	id := agentruntime.AgentID("abc")
	cases := map[string]string{
		agentruntime.EventsSubject(id):  "agent.abc.events",
		agentruntime.ControlSubject(id): "agent.abc.control",
		agentruntime.HealthSubject(id):  "agent.abc.health",
	}
	for got, want := range cases {
		if got != want {
			t.Errorf("subject = %q, want %q", got, want)
		}
	}
}
