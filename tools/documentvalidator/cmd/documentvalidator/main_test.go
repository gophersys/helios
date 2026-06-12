package main

import (
	"bytes"
	"path/filepath"
	"strings"
	"testing"
)

// repoSchemaDir locates the in-repo document schemas relative to this test file:
// tools/documentvalidator/cmd/documentvalidator -> schemas/document/v1.
func repoSchemaDir(t *testing.T) string {
	t.Helper()
	dir, err := filepath.Abs(filepath.Join("..", "..", "..", "..", "schemas", "document", "v1"))
	if err != nil {
		t.Fatalf("resolve schema dir: %v", err)
	}
	return dir
}

// exampleDir locates the worked linkbox example project.
func exampleDir(t *testing.T) string {
	t.Helper()
	return filepath.Join(repoSchemaDir(t), "examples", "linkbox")
}

// runCLI invokes run() with captured output and returns the exit code, stdout,
// and stderr.
func runCLI(args ...string) (int, string, string) {
	var out, errBuf bytes.Buffer
	code := run(args, &out, &errBuf)
	return code, out.String(), errBuf.String()
}

// TestExampleValidatesClean is the load-bearing assertion of the task: the
// worked linkbox example MUST validate clean (exit 0, no violations). Its T6
// coverage report is informational and does not change the exit code.
func TestExampleValidatesClean(t *testing.T) {
	code, stdout, stderr := runCLI("validate", exampleDir(t), "--schemas", repoSchemaDir(t))
	if code != exitClean {
		t.Fatalf("example did not validate clean: exit %d\nstdout:\n%s\nstderr:\n%s", code, stdout, stderr)
	}
	if !strings.Contains(stdout, "ok: 0 violations") {
		t.Errorf("expected clean marker in output, got:\n%s", stdout)
	}
	// The T6 report should still surface REQ-0002 as an uncovered P1 requirement.
	if !strings.Contains(stdout, "REQ-0002") || !strings.Contains(stdout, "T6") {
		t.Errorf("expected T6 coverage report for REQ-0002, got:\n%s", stdout)
	}
}

// TestExampleValidatesCleanJSON checks the JSON surface is clean and well-formed.
func TestExampleValidatesCleanJSON(t *testing.T) {
	code, stdout, _ := runCLI("validate", exampleDir(t), "--schemas", repoSchemaDir(t), "--json")
	if code != exitClean {
		t.Fatalf("expected exit 0, got %d", code)
	}
	if !strings.Contains(stdout, `"ok": true`) {
		t.Errorf("expected ok:true in JSON, got:\n%s", stdout)
	}
	if !strings.Contains(stdout, `"violations": []`) {
		t.Errorf("expected empty violations, got:\n%s", stdout)
	}
}

// TestBrokenFixtures asserts each broken fixture exits 1 and fires the expected
// rule (or schema pointer) in its diagnostics.
func TestBrokenFixtures(t *testing.T) {
	cases := []struct {
		dir       string
		wantRule  string // a substring that must appear in the diagnostics
		wantPhras string // an additional substring to confirm the right diagnostic
	}{
		{"dangling_link", "T1", "does not resolve"},
		{"wrong_direction", "T2", "downstream"},
		{"duplicate_id", "T5", "duplicate id"},
		{"schema_violation", "/data/items/0/priority", "must be one of"},
	}
	schemas := repoSchemaDir(t)
	for _, tc := range cases {
		t.Run(tc.dir, func(t *testing.T) {
			dir := filepath.Join("..", "..", "testdata", tc.dir)
			code, stdout, stderr := runCLI("validate", dir, "--schemas", schemas)
			if code != exitViolations {
				t.Fatalf("expected exit 1 (violations), got %d\nstdout:\n%s\nstderr:\n%s", code, stdout, stderr)
			}
			if !strings.Contains(stdout, tc.wantRule) {
				t.Errorf("expected rule/pointer %q in output, got:\n%s", tc.wantRule, stdout)
			}
			if !strings.Contains(stdout, tc.wantPhras) {
				t.Errorf("expected phrase %q in output, got:\n%s", tc.wantPhras, stdout)
			}
		})
	}
}

// TestLinksCommand checks the links command emits the derived edge list and a
// known upstream edge.
func TestLinksCommand(t *testing.T) {
	code, stdout, stderr := runCLI("links", exampleDir(t))
	if code != exitClean {
		t.Fatalf("links exited %d\nstderr:\n%s", code, stderr)
	}
	if !strings.Contains(stdout, "REQ-0001 --realizes--> PER-0001") {
		t.Errorf("expected a known edge in links output, got:\n%s", stdout)
	}
}

// TestUsageErrors checks usage/IO failures map to exit code 2.
func TestUsageErrors(t *testing.T) {
	if code, _, _ := runCLI(); code != exitUsage {
		t.Errorf("no args: expected exit 2, got %d", code)
	}
	if code, _, _ := runCLI("bogus"); code != exitUsage {
		t.Errorf("unknown command: expected exit 2, got %d", code)
	}
	if code, _, _ := runCLI("validate"); code != exitUsage {
		t.Errorf("missing dir: expected exit 2, got %d", code)
	}
	if code, _, _ := runCLI("validate", filepath.Join("..", "..", "testdata", "does-not-exist")); code != exitUsage {
		t.Errorf("missing dir target: expected exit 2, got %d", code)
	}
}
