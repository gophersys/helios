package checker_test

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/gophersys/hnslint/internal/checker"
)

// fixture returns the absolute path to a testdata library directory.
func fixture(t *testing.T, parts ...string) string {
	t.Helper()
	all := append([]string{"testdata"}, parts...)
	abs, err := filepath.Abs(filepath.Join(all...))
	if err != nil {
		t.Fatalf("resolving fixture %v: %v", parts, err)
	}
	return abs
}

// messages flattens diagnostics to their message text for substring assertions.
func messages(diags []checker.Diagnostic) string {
	var b strings.Builder
	for _, d := range diags {
		b.WriteString(d.String())
		b.WriteByte('\n')
	}
	return b.String()
}

func TestCheckGoodLibraryIsClean(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "good", "configuration"))
	if len(diags) != 0 {
		t.Fatalf("expected no diagnostics for a conformant library, got:\n%s", messages(diags))
	}
}

func TestCheckRejectsWrongModulePath(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-modulepath", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for a wrong module path, got none")
	}
	got := messages(diags)
	if !strings.Contains(got, "module path") {
		t.Errorf("diagnostic should mention the module path, got:\n%s", got)
	}
	if !strings.Contains(got, "github.com/gophersys/libs/go/configuration") {
		t.Errorf("diagnostic should name the expected module path, got:\n%s", got)
	}
}

func TestCheckRejectsWrongPrimaryPackageName(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-package", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for a wrong primary package name, got none")
	}
	got := messages(diags)
	if !strings.Contains(got, "package") {
		t.Errorf("diagnostic should mention the package, got:\n%s", got)
	}
	if !strings.Contains(got, "configuration") {
		t.Errorf("diagnostic should name the expected package, got:\n%s", got)
	}
}

func TestCheckRejectsWrongFakesPackageName(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-fakes", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for a wrong fakes package name, got none")
	}
	got := messages(diags)
	if !strings.Contains(got, "configurationtest") {
		t.Errorf("diagnostic should name the expected fakes package, got:\n%s", got)
	}
}

func TestCheckRejectsBannedSlug(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-bannedslug", "utils"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for a banned directory slug, got none")
	}
	got := messages(diags)
	if !strings.Contains(got, "banned") {
		t.Errorf("diagnostic should mention the banned token, got:\n%s", got)
	}
	if !strings.Contains(got, "utils") {
		t.Errorf("diagnostic should name the offending token, got:\n%s", got)
	}
}

func TestCheckRejectsBannedSubPackage(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-bannedsubpkg", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for a banned sub-package name, got none")
	}
	got := messages(diags)
	if !strings.Contains(got, "banned") {
		t.Errorf("diagnostic should mention the banned token, got:\n%s", got)
	}
	if !strings.Contains(got, "util") {
		t.Errorf("diagnostic should name the offending sub-package, got:\n%s", got)
	}
}

// TestCheckRejectsCfgtestBreak locks in the exact regression ADR-0018 names as
// its motivating case: a fakes package "cfgtest" built on the banned "cfg",
// which forbidigo cannot see because it only inspects the *cfg* identifier.
func TestCheckRejectsCfgtestBreak(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-cfgtest", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for the cfgtest fakes break, got none")
	}
	got := messages(diags)
	if !strings.Contains(got, "cfgtest") {
		t.Errorf("diagnostic should name the offending cfgtest package, got:\n%s", got)
	}
	if !strings.Contains(got, "cfg") {
		t.Errorf("diagnostic should name the banned cfg abbreviation, got:\n%s", got)
	}
}

func TestCheckReportsMissingGoMod(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "missing-gomod", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for a missing go.mod, got none")
	}
	if !strings.Contains(messages(diags), "go.mod") {
		t.Errorf("diagnostic should mention go.mod, got:\n%s", messages(diags))
	}
}

func TestDiagnosticStringFormat(t *testing.T) {
	t.Parallel()

	d := checker.Diagnostic{Path: "libs/go/configuration/go.mod", Message: "bad"}
	if got, want := d.String(), "libs/go/configuration/go.mod: bad"; got != want {
		t.Errorf("Diagnostic.String() = %q, want %q", got, want)
	}
}

func TestDiagnosticsAreDeterministic(t *testing.T) {
	t.Parallel()

	dir := fixture(t, "bad-bannedsubpkg", "configuration")
	first := messages(checker.Check(dir))
	for range 5 {
		if got := messages(checker.Check(dir)); got != first {
			t.Fatalf("Check is non-deterministic:\nfirst:\n%s\nlater:\n%s", first, got)
		}
	}
}

func TestBannedTokenDetection(t *testing.T) {
	t.Parallel()

	banned := []string{"cfg", "config", "deps", "k8s", "mgmt", "obsv", "o11y", "golang", "util", "utils", "common", "core", "misc", "auth", "db", "repo", "store", "ts"}
	for _, tok := range banned {
		if !checker.IsBanned(tok) {
			t.Errorf("IsBanned(%q) = false, want true", tok)
		}
	}
	allowed := []string{"configuration", "dependencies", "observability", "secrets", "errors", "testing", "parse", "tree", "deterministic", "mint", "configurationtest"}
	for _, tok := range allowed {
		if checker.IsBanned(tok) {
			t.Errorf("IsBanned(%q) = true, want false", tok)
		}
	}
}
