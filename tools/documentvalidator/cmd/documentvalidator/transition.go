package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// statusSuperseded and statusApproved are the lifecycle statuses the T5
// transition check reasons about (doc 11 §4 lifecycle).
const (
	statusDraft      = "draft"
	statusReview     = "review"
	statusApproved   = "approved"
	statusSuperseded = "superseded"
)

// checkTransitions enforces the T5 lifecycle rules across a git revision (doc 11
// §4 / §7 T5: an approved document is immutable; supersession is append-only).
// For every document file under dir that differs from its content at gitRef, it
// compares the old envelope to the new one:
//
//   - meta.version must never decrease;
//   - status `superseded` is terminal — it may never return to another status;
//   - if the old status was `approved`, the new revision must either be
//     byte-identical to the old, or carry version = old+1 with status
//     draft|review (the normal amend-by-supersession path), or carry status
//     `superseded` with the version unchanged (retiring the approved revision).
//
// A document that does not exist at gitRef is new — no prior state, nothing to
// check. Diagnostics are reported under rule T5 and stably ordered by the caller.
func checkTransitions(dir, gitRef string) ([]diagnostic, error) {
	repoRoot, err := gitRepoRoot(dir)
	if err != nil {
		return nil, err
	}

	paths, err := walkDocuments(dir)
	if err != nil {
		return nil, err
	}

	var diags []diagnostic
	for _, path := range paths {
		rel := relPath(dir, path)
		repoRel, rerr := repoRelativePath(repoRoot, path)
		if rerr != nil {
			return nil, rerr
		}

		oldBytes, exists, gerr := gitShow(repoRoot, gitRef, repoRel)
		if gerr != nil {
			return nil, gerr
		}
		if !exists {
			// Untracked at the ref: a new document has no prior state to constrain.
			continue
		}

		newBytes, rferr := os.ReadFile(path) //nolint:gosec // path from the operator-chosen directory walk.
		if rferr != nil {
			return nil, fmt.Errorf("read %s: %w", path, rferr)
		}

		oldMeta, omerr := projectMeta(path, oldBytes)
		if omerr != nil {
			// The prior revision did not project (e.g. malformed at that ref). Report
			// it under T5 rather than failing the whole run.
			diags = append(diags, diagnostic{
				File:    rel,
				Rule:    "T5",
				Message: fmt.Sprintf("could not project the %s revision for the transition check: %v", gitRef, omerr),
			})
			continue
		}
		newMeta, nmerr := projectMeta(path, newBytes)
		if nmerr != nil {
			// The new revision's own projection failure is surfaced by the shape
			// pass; skip the transition comparison rather than double-reporting.
			continue
		}

		identical := bytes.Equal(oldBytes, newBytes)
		diags = append(diags, transitionDiagnostics(rel, oldMeta, newMeta, identical)...)
	}
	return diags, nil
}

// envelopeMeta is the slice of the envelope the transition check reads: the
// document id, its monotonic version, and its lifecycle status. okVersion is
// false when meta.version is absent or non-numeric (then the monotonicity rule
// is not applied — shape validation owns "version is required/numeric").
type envelopeMeta struct {
	id        string
	version   int
	okVersion bool
	status    string
}

// transitionDiagnostics applies the T5 rules to one document's old/new envelope.
func transitionDiagnostics(rel string, old, current envelopeMeta, identical bool) []diagnostic {
	id := current.id
	if id == "" {
		id = old.id
	}
	mk := func(message string) diagnostic {
		return diagnostic{File: rel, DocumentID: id, Rule: "T5", Message: message}
	}

	var diags []diagnostic

	// (1) Version is monotonic — it may never decrease.
	if old.okVersion && current.okVersion && current.version < old.version {
		diags = append(diags, mk(fmt.Sprintf(
			"meta.version decreased from %d to %d (version is monotonic)", old.version, current.version)))
	}

	// (2) `superseded` is terminal — it may never return to another status.
	if old.status == statusSuperseded && current.status != statusSuperseded {
		diags = append(diags, mk(fmt.Sprintf(
			"status moved from superseded to %q (superseded is terminal)", current.status)))
	}

	// (3) An approved document is immutable except via the sanctioned paths.
	if old.status == statusApproved && !identical {
		if !approvedTransitionAllowed(old, current) {
			diags = append(diags, mk(approvedViolationMessage(old, current)))
		}
	}

	return diags
}

// approvedTransitionAllowed reports whether a non-identical change to a
// previously-approved document is one of the two sanctioned transitions:
//
//	(b) version = old+1 AND status draft|review (amend-by-supersession), or
//	(c) status superseded with version unchanged (retire the approved revision).
func approvedTransitionAllowed(old, current envelopeMeta) bool {
	// (b) bump to a new draft/review revision.
	if (current.status == statusDraft || current.status == statusReview) &&
		old.okVersion && current.okVersion && current.version == old.version+1 {
		return true
	}
	// (c) mark the approved revision superseded in place.
	if current.status == statusSuperseded &&
		old.okVersion && current.okVersion && current.version == old.version {
		return true
	}
	return false
}

// approvedViolationMessage explains why a non-identical change to an approved
// document is rejected.
func approvedViolationMessage(old, current envelopeMeta) string {
	return fmt.Sprintf(
		"approved document was modified illegally (was version %d/%s, now version %d/%s): "+
			"an approved document must be byte-identical, or bump to version %d with status draft|review, "+
			"or move to status superseded at the same version",
		old.version, old.status, current.version, current.status, old.version+1)
}

// projectMeta projects a document's raw bytes and extracts the transition-check
// fields of its envelope. The path is used only to choose the projection surface
// by extension (.md vs .yaml).
func projectMeta(path string, raw []byte) (envelopeMeta, error) {
	doc, err := projection.ProjectBytes(path, raw)
	if err != nil {
		return envelopeMeta{}, err
	}
	meta, _ := doc.Projection["meta"].(map[string]any)
	out := envelopeMeta{}
	if meta != nil {
		out.id, _ = meta["id"].(string)
		out.status, _ = meta["status"].(string)
		out.version, out.okVersion = asInt(meta["version"])
	}
	return out, nil
}

// asInt coerces a projected numeric value (YAML/JSON numbers arrive as int or
// float64) to an int, reporting whether it was numeric.
func asInt(v any) (int, bool) {
	switch n := v.(type) {
	case int:
		return n, true
	case int64:
		return int(n), true
	case float64:
		return int(n), true
	default:
		return 0, false
	}
}

// gitRepoRoot returns the git work-tree root that contains dir.
func gitRepoRoot(dir string) (string, error) {
	out, err := runGit(dir, "rev-parse", "--show-toplevel")
	if err != nil {
		return "", fmt.Errorf("locating git repo for %s: %w", dir, err)
	}
	return strings.TrimSpace(string(out)), nil
}

// repoRelativePath renders an absolute (or working-relative) document path as a
// forward-slash path relative to the repo root, the form `git show ref:path`
// expects. Both sides are passed through filepath.EvalSymlinks first so a repo
// root reported through a symlink (e.g. macOS /var -> /private/var under
// t.TempDir()) lines up with the document's real path; otherwise filepath.Rel
// would emit a spurious "../.." escape and git would reject the path.
func repoRelativePath(repoRoot, path string) (string, error) {
	root := evalSymlinks(repoRoot)
	abs, err := filepath.Abs(path)
	if err != nil {
		return "", fmt.Errorf("absolute path for %s: %w", path, err)
	}
	abs = evalSymlinks(abs)
	rel, err := filepath.Rel(root, abs)
	if err != nil {
		return "", fmt.Errorf("relativizing %s against %s: %w", abs, root, err)
	}
	return filepath.ToSlash(rel), nil
}

// evalSymlinks resolves a path's symlinks, falling back to the original path when
// resolution fails (e.g. the path does not yet exist) so callers always get a
// usable value.
func evalSymlinks(path string) string {
	if resolved, err := filepath.EvalSymlinks(path); err == nil {
		return resolved
	}
	return path
}

// gitShow returns the content of repoRel at gitRef. The second return value is
// false (with a nil error) when the path does not exist at that ref — a new
// document — which git reports as a "does not exist" / "exists on disk, but
// not in" error that this function distinguishes from a real git failure.
func gitShow(repoRoot, gitRef, repoRel string) ([]byte, bool, error) {
	spec := gitRef + ":" + repoRel
	out, stderr, err := runGitCapture(repoRoot, "show", spec)
	if err == nil {
		return out, true, nil
	}
	if isGitMissingPath(stderr) {
		return nil, false, nil
	}
	return nil, false, fmt.Errorf("git show %s: %w: %s", spec, err, strings.TrimSpace(stderr))
}

// isGitMissingPath reports whether git's stderr indicates the path is absent at
// the ref (a new document) rather than a genuine failure (bad ref, not a repo).
func isGitMissingPath(stderr string) bool {
	s := strings.ToLower(stderr)
	return strings.Contains(s, "does not exist") ||
		strings.Contains(s, "exists on disk, but not in") ||
		strings.Contains(s, "path does not exist")
}

// runGit runs a git subcommand in repoOrDir and returns its stdout, failing on a
// non-zero exit.
func runGit(repoOrDir string, args ...string) ([]byte, error) {
	out, stderr, err := runGitCapture(repoOrDir, args...)
	if err != nil {
		return nil, fmt.Errorf("%w: %s", err, strings.TrimSpace(stderr))
	}
	return out, nil
}

// runGitCapture runs git with -C repoOrDir, returning stdout, stderr, and the
// run error separately so callers can classify failures (e.g. missing path).
func runGitCapture(repoOrDir string, args ...string) (stdout []byte, stderr string, err error) {
	full := append([]string{"-C", repoOrDir}, args...)
	cmd := exec.Command("git", full...) //nolint:gosec // args are validator-controlled, repoOrDir is operator-chosen.
	var outBuf, errBuf bytes.Buffer
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	err = cmd.Run()
	return outBuf.Bytes(), errBuf.String(), err
}
