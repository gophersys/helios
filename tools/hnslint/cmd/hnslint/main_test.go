package main

import (
	"bytes"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// libsRoot resolves the repo's libs/go directory from the tool's location, so
// the CLI test exercises hnslint against the real libraries.
func libsRoot(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd() // .../tools/hnslint/cmd/hnslint
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	root := filepath.Join(wd, "..", "..", "..", "..", "libs", "go")
	if _, err := os.Stat(root); err != nil {
		t.Skipf("libs/go not reachable from %s: %v", wd, err)
	}
	abs, _ := filepath.Abs(root)
	return abs
}

func TestRunNoArgsIsUsageError(t *testing.T) {
	t.Parallel()
	var out bytes.Buffer
	code, err := run(nil, &out)
	if code != 2 {
		t.Errorf("run() with no args exit = %d, want 2", code)
	}
	if !errors.Is(err, errUsage) {
		t.Errorf("run() with no args err = %v, want errUsage", err)
	}
}

func TestRunCleanLibraryExitsZero(t *testing.T) {
	t.Parallel()
	dir := filepath.Join(libsRoot(t), "configuration")
	var out bytes.Buffer
	code, err := run([]string{dir}, &out)
	if code != 0 || err != nil {
		t.Errorf("run(%s) = (%d, %v), want (0, nil); output:\n%s", dir, code, err, out.String())
	}
	if strings.TrimSpace(out.String()) != "" {
		t.Errorf("expected no diagnostics for a conformant library, got:\n%s", out.String())
	}
}

func TestRunNonDirectoryExitsOne(t *testing.T) {
	t.Parallel()
	var out bytes.Buffer
	code, _ := run([]string{filepath.Join(t.TempDir(), "does-not-exist")}, &out)
	if code != 1 {
		t.Errorf("run(missing) exit = %d, want 1", code)
	}
	if !strings.Contains(out.String(), "not a directory") {
		t.Errorf("expected a not-a-directory diagnostic, got:\n%s", out.String())
	}
}

func TestRunReportsViolationsAndExitsOne(t *testing.T) {
	t.Parallel()
	// A bad testdata fixture (wrong module path) lives under the checker package.
	wd, _ := os.Getwd()
	bad := filepath.Join(wd, "..", "..", "internal", "checker", "testdata", "bad-modulepath", "configuration")
	if _, err := os.Stat(bad); err != nil {
		t.Skipf("fixture unreachable: %v", err)
	}
	var out bytes.Buffer
	code, err := run([]string{bad}, &out)
	if code != 1 || err != nil {
		t.Errorf("run(bad) = (%d, %v), want (1, nil)", code, err)
	}
	if !strings.Contains(out.String(), "module path") {
		t.Errorf("expected a module-path diagnostic, got:\n%s", out.String())
	}
}
