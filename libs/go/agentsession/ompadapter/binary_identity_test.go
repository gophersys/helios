package ompadapter_test

import (
	"testing"

	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// TestVerifyOmpBinary_RejectsOhMyPosh is F6: the adapter must not drive the WRONG `omp`.
//
// `omp` is also oh-my-posh's binary name, and on this host a bare `omp` resolves to oh-my-posh, so
// a plan that "just runs omp" runs a prompt theme engine as if it were the coding agent — the rpc
// handshake never comes and the session hangs to its deadline. So before it drives the binary the
// adapter checks the `--version` line: the coding agent prints `omp/<semver>` (captured:
// q1-install-verify.txt:15, `omp/17.3.7`); oh-my-posh prints a bare semver (this host: 15.10.0).
// A binary that is not the coding agent is REJECTED, not driven.
//
// This is the guard chosen over authoring the live real-omp lane here: libs CI installs no harness
// and holds no credential, so the credential-free real-omp frame proof (plan test #15) lands at
// PR-2's eden lane, not in this PR. The plan's "AUTHORED here" claim for #15 is therefore dropped;
// this guard is what PR-1b pins instead.
func TestVerifyOmpBinary_RejectsOhMyPosh(t *testing.T) {
	t.Parallel()

	rejected := []struct {
		name    string
		version string
	}{
		{"oh-my-posh bare semver on this host", "15.10.0"},
		{"oh-my-posh with its name", "oh-my-posh 15.10.0"},
		{"a future oh-my-posh in the coding agent's major", "19.2.1"},
		{"empty output (not a version at all)", ""},
	}
	for _, tc := range rejected {
		if err := ompadapter.VerifyOmpBinaryForTest(tc.version); err == nil {
			t.Errorf("%s: %q was ACCEPTED as the omp coding agent — driving oh-my-posh as the agent hangs on a handshake that never comes",
				tc.name, tc.version)
		}
	}

	accepted := []struct {
		name    string
		version string
	}{
		{"the captured coding-agent version", "omp/17.3.7"},
		{"the pinned window's lower bound", "omp/17.2.5"},
	}
	for _, tc := range accepted {
		if err := ompadapter.VerifyOmpBinaryForTest(tc.version); err != nil {
			t.Errorf("%s: the omp coding agent %q must be accepted: %v", tc.name, tc.version, err)
		}
	}
}
