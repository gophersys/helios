package claudeadapter_test

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f)): a credential value handed
// to the adapter through the REAL InjectedCredential / Secret.Use path that must appear in
// NO surfaced artifact — not an emitted Event, not a Command echo, not an error string, not
// the spawn argument vector. It is a FAKE token (never a live credential), distinctive
// enough that any leak is unambiguous.
const seededCanary = "SEEDED-CANARY-claude-a1b2c3d4e5f6-do-not-leak"

// TestCanary_CredentialNeverLeaksThroughStream threads the seeded canary through the
// adapter's GENUINE credential path — secretstest.MintSecret -> InjectedCredential ->
// Spawn -> Secret.Use -> child env — over a REAL stub subprocess, drains the whole
// normalized stream, and asserts the canary surfaces on NO event. The child env injection
// is the only place the plaintext is allowed to land; the stream, the args, and any error
// must be canary-free. This is the credential-never-leaks guarantee on the real spawn path.
func TestCanary_CredentialNeverLeaksThroughStream(t *testing.T) {
	t.Parallel()
	stub := buildCanaryStub(t)

	adapter := claudeadapter.MustNewForTest(t, claudeadapter.Config{Binary: stub})
	conn, err := adapter.Spawn(
		context.Background(),
		agentsession.Spec{Workspace: t.TempDir(), Routing: agentsession.RouteKey{Role: "assistant"}},
		agentsession.Route{Harness: "claude-code", Model: "stub-fable"},
		agentsession.InjectedCredential{
			Secret:  secretstest.MintSecret([]byte(seededCanary)),
			Vehicle: agentsession.VehicleEnv,
			EnvName: "CLAUDE_CODE_OAUTH_TOKEN",
		},
	)
	if err != nil {
		// Even the error path must not embed the credential.
		if strings.Contains(err.Error(), seededCanary) {
			t.Fatalf("canary leaked into the Spawn error: %v", err)
		}
		t.Fatalf("Spawn over the stub: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := conn.Send(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: "make a file"}); err != nil {
		if strings.Contains(err.Error(), seededCanary) {
			t.Fatalf("canary leaked into a Send error: %v", err)
		}
		t.Fatalf("Send: %v", err)
	}

	// A background drainer collects every event to EOF; the conn's Close ladder waits on the
	// scanner, which finishes only once the channel is read to completion (the conn is not
	// self-draining). Close then unblocks the scanner and the drainer reports the full stream.
	collected := make(chan []agentsession.Event, 1)
	go func() {
		var events []agentsession.Event
		for ev := range conn.Events() {
			events = append(events, ev)
		}
		collected <- events
	}()

	// Close must reap without surfacing the credential in its error.
	if cerr := conn.Close(ctx); cerr != nil && strings.Contains(cerr.Error(), seededCanary) {
		t.Fatalf("canary leaked into the Close error: %v", cerr)
	} else if cerr != nil {
		t.Fatalf("Close: %v", cerr)
	}

	var events []agentsession.Event
	select {
	case events = <-collected:
	case <-ctx.Done():
		t.Fatalf("timed out draining the canary stream: %v", ctx.Err())
	}
	if len(events) == 0 {
		t.Fatal("the stub subprocess produced no events")
	}
	// The whole-stream redaction guarantee: no event field carries the canary.
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], seededCanary)
	}
}

// TestCanary_NeverInSpawnArguments asserts the seeded canary is NEVER placed on the spawn
// argument vector (the credential rides the child ENV, never argv — argv is world-readable
// via /proc). buildArguments is pure, so this is a fast, deterministic guard.
func TestCanary_NeverInSpawnArguments(t *testing.T) {
	t.Parallel()
	spec := agentsession.Spec{
		Grants:      []agentsession.ToolGrant{{ID: "g", Tool: "Write"}},
		SystemHints: "be terse",
		ResumeFrom:  "sess-1",
	}
	args := claudeadapter.BuildArgumentsForTest(spec, agentsession.Route{Model: "stub-fable"})
	for _, a := range args {
		if strings.Contains(a, seededCanary) {
			t.Fatalf("canary present in a spawn argument: %q", a)
		}
	}
}

// TestCanary_InjectionReachesChildEnv is the NON-VACUITY anchor for the redaction property:
// it proves the credential path is REAL by asserting the canary DOES land on the child env
// (exactly once, on the var the CLI reads) while being scrubbed of the higher-precedence
// keys. If this failed, the stream-leak test above would pass vacuously (a credential that
// never reached the child cannot leak). The plaintext appearing HERE — on the child env, the
// one sanctioned destination — and NOWHERE on the stream is the whole guarantee.
func TestCanary_InjectionReachesChildEnv(t *testing.T) {
	t.Parallel()
	base := []string{
		"PATH=/usr/bin",
		"ANTHROPIC_API_KEY=stray-precedence-key",
	}
	env := claudeadapter.ChildEnvironmentForTest(base, "CLAUDE_CODE_OAUTH_TOKEN", seededCanary)

	found := 0
	for _, e := range env {
		if e == "CLAUDE_CODE_OAUTH_TOKEN="+seededCanary {
			found++
		}
		if strings.HasPrefix(e, "ANTHROPIC_API_KEY=") {
			t.Errorf("higher-precedence key survived the scrub: %q", e)
		}
	}
	if found != 1 {
		t.Fatalf("the canary must reach the child env exactly once (the sanctioned destination), got %d", found)
	}
}

// buildCanaryStub compiles the stub harness into t.TempDir() and returns its path.
func buildCanaryStub(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	binary := filepath.Join(dir, "stubharness")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("cannot locate the test source path")
	}
	source := filepath.Join(filepath.Dir(file), "internal", "stubharness")
	// #nosec G204 -- fixed `go build` of the in-repo stub; binary/source are test-derived paths, not user input.
	build := exec.Command("go", "build", "-o", binary, ".")
	build.Dir = source
	build.Env = os.Environ()
	if out, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build stub harness: %v\n%s", err, out)
	}
	return binary
}
