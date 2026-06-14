package gitrepository_test

import (
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
	"github.com/gophersys/libs/go/gitrepository/gitrepositorytest"
)

// sink keeps the benchmarked work observable so the compiler cannot prove the result dead and
// elide it (a package-level `any` per ADR-0020 dimension (g); kept OFF any sentinel path).
//
//nolint:gochecknoglobals // benchmark sink must be package-level so the compiler cannot elide the work.
var sink any

// benchNames is a representative branch-name batch the validation spine folds per iteration. A
// batch (rather than a single sub-nanosecond op) keeps the per-iteration wall time well above
// benchstat's noise floor so the bench-guard regression check is stable run-to-run (the
// deterministic allocs/op stays the load-bearing signal; ADR-0020 §g).
//
//nolint:gochecknoglobals // a shared read-only benchmark fixture.
var benchNames = []string{
	"main", "feature/x", "release/2026.06", "a/b/c", "fix-123",
	"feature/long-descriptive-branch-name", "hotfix/2026.06.13", "wip/agent-run-42",
}

// benchHexes is a representative object-id batch the normalizer folds per iteration.
//
//nolint:gochecknoglobals // a shared read-only benchmark fixture.
var benchHexes = []string{
	"0123456789ABCDEF0123456789abcdef01234567",
	"abcdef0123456789abcdef0123456789abcdef01",
	"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
	"  fedcba9876543210fedcba9876543210fedcba98  ",
}

// BenchmarkNew measures the pure constructor spine — the New(configuration, dependencies) fold
// the orchestrator runs once per worked checkout / derived worktree. It validates Config+Deps,
// copies the remotes map, and allocates the lock table; no I/O, no clock read.
func BenchmarkNew(b *testing.B) {
	backend := gitrepositorytest.New()
	configuration := gitrepository.Config{
		Root:    "/abs/root",
		Remotes: map[string]string{"origin": "https://github.com/acme/app.git", "eden": "https://eden.example/app.git"},
	}
	dependencies := gitrepository.Deps{Backend: backend, Clock: stubClock{}}
	b.ReportAllocs()
	var (
		repository *gitrepository.Repository
		err        error
	)
	for b.Loop() {
		repository, err = gitrepository.New(configuration, dependencies)
	}
	sink = repository
	if err != nil {
		b.Fatalf("New: %v", err)
	}
}

// BenchmarkParseBranchName measures the branch-name validation spine — the argv-injection guard
// run on EVERY worktree/branch/push op before a name reaches a git argv. It folds a representative
// batch per iteration (the full byte/affix/component pass over varied names).
func BenchmarkParseBranchName(b *testing.B) {
	b.ReportAllocs()
	var parsed gitrepository.BranchName
	for b.Loop() {
		for _, name := range benchNames {
			p, err := gitrepository.ParseBranchName(name)
			if err != nil {
				b.Fatalf("ParseBranchName(%q): %v", name, err)
			}
			parsed = p
		}
	}
	sink = parsed
}

// BenchmarkCommitIDFromHex measures the object-id normalizer — run per commit id a Backend
// resolves from git output (trim + length check + hex validation + lowercase fold). Folds a
// representative batch (sha-1, sha-256, and a whitespace-padded mixed-case id) per iteration.
func BenchmarkCommitIDFromHex(b *testing.B) {
	b.ReportAllocs()
	var id gitrepository.CommitID
	for b.Loop() {
		for _, hex := range benchHexes {
			id = gitrepository.CommitIDFromHex(hex)
		}
	}
	sink = id
}

// BenchmarkWrapAndClassify measures the typed-error wrap+classify boundary end-to-end — the seam
// a Backend and the library run on every error: WrapError mints the Kind-classified chain, and
// KindOf reads it back at the transport boundary. Folding wrap→classify over the error taxonomy
// per iteration keeps the per-iteration time above benchstat's noise floor.
func BenchmarkWrapAndClassify(b *testing.B) {
	typed := []error{
		&gitrepository.NonFastForwardError{},
		&gitrepository.AuthError{Remote: "origin"},
		&gitrepository.NotFoundError{What: "ref"},
		&gitrepository.InvalidRefError{Ref: "x"},
	}
	b.ReportAllocs()
	var kind errors.Kind
	for b.Loop() {
		for _, e := range typed {
			kind = errors.KindOf(gitrepository.WrapError(e))
		}
	}
	sink = kind
}
