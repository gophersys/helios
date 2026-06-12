package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// gitRepo is a throwaway git repository created under t.TempDir() for the
// transition-check tests. It commits a v1 corpus, then lets each test mutate the
// working tree and assert the T5 transition check's behaviour against the v1 ref.
type gitRepo struct {
	t   *testing.T
	dir string
}

// newGitRepo initializes an empty git repo in a fresh temp dir with a
// deterministic identity, so commits succeed in a clean CI environment.
func newGitRepo(t *testing.T) *gitRepo {
	t.Helper()
	dir := t.TempDir()
	r := &gitRepo{t: t, dir: dir}
	r.git("init", "-q")
	r.git("config", "user.email", "validator@example.test")
	r.git("config", "user.name", "Validator Test")
	r.git("config", "commit.gpgsign", "false")
	return r
}

// git runs a git subcommand in the repo, failing the test on error.
func (r *gitRepo) git(args ...string) string {
	r.t.Helper()
	cmd := exec.Command("git", append([]string{"-C", r.dir}, args...)...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		r.t.Fatalf("git %s: %v\n%s", strings.Join(args, " "), err, out)
	}
	return string(out)
}

// write writes a document file (creating parent dirs) into the working tree.
func (r *gitRepo) write(name, content string) {
	r.t.Helper()
	path := filepath.Join(r.dir, name)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		r.t.Fatalf("mkdir for %s: %v", name, err)
	}
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		r.t.Fatalf("write %s: %v", name, err)
	}
}

// commitAll stages everything and commits, returning nothing (the ref is HEAD).
func (r *gitRepo) commitAll(message string) {
	r.t.Helper()
	r.git("add", "-A")
	r.git("commit", "-q", "-m", message)
}

// approvedDoc renders a minimal, well-formed requirements envelope at the given
// version and status. Only the envelope fields the transition check reads
// (id/version/status) are load-bearing; the rest keeps it projectable.
func approvedDoc(version int, status string) string {
	return "meta:\n" +
		"  id: requirements\n" +
		"  type: requirements\n" +
		"  status: " + status + "\n" +
		"  version: " + itoa(version) + "\n" +
		"data:\n" +
		"  items: []\n"
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b []byte
	neg := n < 0
	if neg {
		n = -n
	}
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	if neg {
		b = append([]byte{'-'}, b...)
	}
	return string(b)
}

// hasT5 reports whether any diagnostic is a T5 finding, and returns the joined
// messages for assertion context.
func hasT5(diags []diagnostic) (bool, string) {
	var msgs []string
	found := false
	for _, d := range diags {
		if d.Rule == "T5" {
			found = true
		}
		msgs = append(msgs, d.Rule+": "+d.Message)
	}
	return found, strings.Join(msgs, "\n")
}

// setupApprovedV1 builds a repo whose committed v1 state is an approved,
// version-1 requirements document, and returns the repo plus the path to mutate.
func setupApprovedV1(t *testing.T) *gitRepo {
	r := newGitRepo(t)
	r.write("requirements.yaml", approvedDoc(1, "approved"))
	r.commitAll("v1 approved")
	return r
}

func TestTransitionApprovedByteIdenticalIsClean(t *testing.T) {
	r := setupApprovedV1(t)
	// No mutation: the working tree equals HEAD — byte-identical, legal (case a).
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); found {
		t.Fatalf("byte-identical approved doc must be clean, got T5:\n%s", msgs)
	}
}

func TestTransitionApprovedMutatedInPlaceFiresT5(t *testing.T) {
	r := setupApprovedV1(t)
	// Mutate the body but keep status approved / version 1 — illegal (case: an
	// approved document is immutable).
	r.write("requirements.yaml", "meta:\n  id: requirements\n  type: requirements\n  status: approved\n  version: 1\ndata:\n  items:\n    - id: REQ-0001\n")
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	found, msgs := hasT5(diags)
	if !found {
		t.Fatalf("mutating an approved doc in place must fire T5, got:\n%s", msgs)
	}
	if !strings.Contains(msgs, "approved document was modified illegally") {
		t.Errorf("unexpected T5 message:\n%s", msgs)
	}
}

func TestTransitionApprovedBumpToDraftIsClean(t *testing.T) {
	r := setupApprovedV1(t)
	// Legal case (b): version 1 -> 2, status approved -> draft.
	r.write("requirements.yaml", approvedDoc(2, "draft"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); found {
		t.Fatalf("approved -> draft at version+1 must be clean, got T5:\n%s", msgs)
	}
}

func TestTransitionApprovedBumpToReviewIsClean(t *testing.T) {
	r := setupApprovedV1(t)
	// Legal case (b): review is also a permitted target status at version+1.
	r.write("requirements.yaml", approvedDoc(2, "review"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); found {
		t.Fatalf("approved -> review at version+1 must be clean, got T5:\n%s", msgs)
	}
}

func TestTransitionApprovedToSupersededSameVersionIsClean(t *testing.T) {
	r := setupApprovedV1(t)
	// Legal case (c): status approved -> superseded, version unchanged.
	r.write("requirements.yaml", approvedDoc(1, "superseded"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); found {
		t.Fatalf("approved -> superseded at same version must be clean, got T5:\n%s", msgs)
	}
}

func TestTransitionApprovedToDraftWithoutVersionBumpFiresT5(t *testing.T) {
	r := setupApprovedV1(t)
	// status approved -> draft but version stays 1: not the sanctioned bump.
	r.write("requirements.yaml", approvedDoc(1, "draft"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); !found {
		t.Fatalf("approved -> draft without a version bump must fire T5, got:\n%s", msgs)
	}
}

func TestTransitionApprovedToSupersededWithVersionBumpFiresT5(t *testing.T) {
	r := setupApprovedV1(t)
	// status approved -> superseded but version also bumped: case (c) requires the
	// version unchanged, so this is illegal.
	r.write("requirements.yaml", approvedDoc(2, "superseded"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); !found {
		t.Fatalf("approved -> superseded with a version bump must fire T5, got:\n%s", msgs)
	}
}

func TestTransitionVersionDecreaseFiresT5(t *testing.T) {
	r := newGitRepo(t)
	// Commit a draft v3, then regress the version to 2 — version must be monotonic
	// regardless of status.
	r.write("requirements.yaml", approvedDoc(3, "draft"))
	r.commitAll("v3 draft")
	r.write("requirements.yaml", approvedDoc(2, "draft"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	found, msgs := hasT5(diags)
	if !found {
		t.Fatalf("a version decrease must fire T5, got:\n%s", msgs)
	}
	if !strings.Contains(msgs, "version decreased") {
		t.Errorf("expected a version-decrease T5 message, got:\n%s", msgs)
	}
}

func TestTransitionSupersededIsTerminal(t *testing.T) {
	r := newGitRepo(t)
	// Commit a superseded v2, then try to revive it to draft at a higher version.
	r.write("requirements.yaml", approvedDoc(2, "superseded"))
	r.commitAll("v2 superseded")
	r.write("requirements.yaml", approvedDoc(3, "draft"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	found, msgs := hasT5(diags)
	if !found {
		t.Fatalf("reviving a superseded doc must fire T5, got:\n%s", msgs)
	}
	if !strings.Contains(msgs, "superseded is terminal") {
		t.Errorf("expected a terminal-superseded T5 message, got:\n%s", msgs)
	}
}

func TestTransitionUntrackedAtRefIsNewAndClean(t *testing.T) {
	r := setupApprovedV1(t)
	// A brand-new document that did not exist at HEAD has no prior state: legal.
	r.write("user-workflows.yaml", "meta:\n  id: user-workflows\n  type: user-workflows\n  status: draft\n  version: 1\ndata:\n  items: []\n")
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); found {
		t.Fatalf("a new (untracked-at-ref) document must be clean, got T5:\n%s", msgs)
	}
}

func TestTransitionDraftToApprovedIsClean(t *testing.T) {
	r := newGitRepo(t)
	// A normal forward gate: draft v1 -> approved v1 (not previously approved, so
	// the immutability rule does not apply; version did not decrease).
	r.write("requirements.yaml", approvedDoc(1, "draft"))
	r.commitAll("v1 draft")
	r.write("requirements.yaml", approvedDoc(1, "approved"))
	diags, err := checkTransitions(r.dir, "HEAD")
	if err != nil {
		t.Fatalf("checkTransitions: %v", err)
	}
	if found, msgs := hasT5(diags); found {
		t.Fatalf("draft -> approved must be clean, got T5:\n%s", msgs)
	}
}

// TestTransitionThroughValidateCLI exercises the --against flag end-to-end:
// an illegal in-place mutation of an approved document must make `validate`
// exit 1 with a T5 diagnostic. Schemas come from the in-repo set so the shape
// pass is satisfied by the minimal-but-valid envelope.
func TestTransitionThroughValidateCLI(t *testing.T) {
	r := newGitRepo(t)
	r.write("requirements.yaml", validRequirementsDoc(1, "approved"))
	r.commitAll("v1 approved")
	// Illegal: mutate body, keep approved/v1.
	r.write("requirements.yaml", validRequirementsDoc(1, "approved")+
		"    - id: REQ-0002\n      statement: \"WHEN x THE SYSTEM SHALL y.\"\n      kind: functional\n      priority: P2\n      rationale: \"r\"\n      acceptance: [\"a\"]\n")

	code, stdout, stderr := runCLI("validate", r.dir, "--schemas", repoSchemaDir(t), "--against", "HEAD")
	if code != exitViolations {
		t.Fatalf("expected exit 1 from illegal transition, got %d\nstdout:\n%s\nstderr:\n%s", code, stdout, stderr)
	}
	if !strings.Contains(stdout, "T5") || !strings.Contains(stdout, "approved document was modified illegally") {
		t.Errorf("expected a T5 transition diagnostic, got:\n%s", stdout)
	}
}

// validRequirementsDoc renders a schema-valid requirements document with one
// requirement, at the given version/status. Used by the CLI-level transition
// test where the shape pass also runs.
func validRequirementsDoc(version int, status string) string {
	return "meta:\n" +
		"  id: requirements\n" +
		"  type: requirements\n" +
		"  schema_version: 1.0.0\n" +
		"  project: linkbox\n" +
		"  status: " + status + "\n" +
		"  version: " + itoa(version) + "\n" +
		"  created: 2026-06-12\n" +
		"  updated: 2026-06-12\n" +
		"  authors:\n" +
		"    - human: mateo\n" +
		"  links:\n" +
		"    realizes: []\n" +
		"    supersedes: null\n" +
		"    informs: []\n" +
		"data:\n" +
		"  items:\n" +
		"    - id: REQ-0001\n" +
		"      statement: \"WHEN a user does a thing THE SYSTEM SHALL respond.\"\n" +
		"      kind: functional\n" +
		"      priority: P2\n" +
		"      rationale: \"Because the product needs it.\"\n" +
		"      acceptance:\n" +
		"        - \"It works.\"\n"
}
