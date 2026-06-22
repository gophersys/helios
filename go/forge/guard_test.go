package forge_test

import (
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
)

// TestGuardDelete_RefusesProtectedNames proves the protected denylist: the load-bearing Eden
// repositories can NEVER pass the guard, case-insensitively, regardless of owner.
func TestGuardDelete_RefusesProtectedNames(t *testing.T) {
	t.Parallel()
	for _, name := range []string{
		"eden", "Eden", "EDEN", "helios", "libs", "LIBS", "template", "templates",
		"infrastructure", ".devcontainer", "devcontainer", "application-templates",
		"iotea-archive", "gophersys", ".github", "config",
	} {
		err := forge.GuardDelete("gophersys", name)
		if err == nil {
			t.Fatalf("GuardDelete MUST refuse protected repository %q (it returned nil)", name)
		}
		if !errors.IsType[forge.ForbiddenDeletionError](err) {
			t.Fatalf("refusing %q should be a ForbiddenDeletionError, got %T: %v", name, err, err)
		}
		if errors.KindOf(forge.Wrap(err)) != errors.KindInvalid {
			t.Fatalf("a refused delete of %q must classify KindInvalid", name)
		}
	}
}

// TestGuardDelete_RefusesNonEphemeral proves the allowlist: anything that is not the reserved
// ephemeral `eden-it-*` shape is refused — real project/app names, near-misses, and the bare prefix.
func TestGuardDelete_RefusesNonEphemeral(t *testing.T) {
	t.Parallel()
	for _, name := range []string{
		"my-app", "project-1", "cool-startup", "eden2", "edenit", "eden-it", "eden-it-",
		"eden-it-x", "Eden-It-abc", "eden_it_abc", "xeden-it-abc", "random", "test", "main",
	} {
		if err := forge.GuardDelete("MateoSegura", name); err == nil {
			t.Fatalf("GuardDelete MUST refuse non-ephemeral repository %q (it returned nil)", name)
		}
	}
}

// TestGuardDelete_AllowsEphemeral proves the ONLY shape the guard permits: disposable `eden-it-*`
// test repositories. (These are never a real repo — no real repository carries this prefix.)
func TestGuardDelete_AllowsEphemeral(t *testing.T) {
	t.Parallel()
	for _, name := range []string{"eden-it-abc", "eden-it-lq3k9xz2", "eden-it-1234567890", "eden-it-saga-001"} {
		if err := forge.GuardDelete("MateoSegura", name); err != nil {
			t.Fatalf("GuardDelete MUST allow ephemeral test repository %q, got: %v", name, err)
		}
		if !forge.EphemeralRepoName(name) {
			t.Fatalf("EphemeralRepoName(%q) should be true", name)
		}
	}
}
