package checker_test

import (
	"strings"
	"testing"

	"github.com/gophersys/hnslint/internal/checker"
)

// TestCheckRejectsBareBannedIdentifier locks check (1): an exported identifier whose
// WHOLE name is a bare banned token (Auth/Store/Db/DB/Repo) is flagged — across type,
// field, and method declarations — the surface forbidigo's lowercase patterns cannot
// see on a capitalized identifier.
func TestCheckRejectsBareBannedIdentifier(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-bannedidentifier", "identity"))
	if len(diags) == 0 {
		t.Fatal("expected diagnostics for bare banned exported identifiers, got none")
	}
	got := messages(diags)

	for _, want := range []string{
		`exported type "Auth"`,
		`exported struct field "Repo"`,
		`exported method "Store"`,
	} {
		if !strings.Contains(got, want) {
			t.Errorf("expected a diagnostic for %s, got:\n%s", want, got)
		}
	}
}

// TestCheckAllowsMeaningfulCompounds is the non-vacuity guard for check (1): a
// meaningful compound that merely CONTAINS a banned word — ObjectStore, DesiredStore,
// PostgresStore, TemplateStore, Author, OAuth — must NOT be flagged. The whole
// good-compounds library (plus the idiomatic Config/Deps spine types) is clean.
func TestCheckAllowsMeaningfulCompounds(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "good-compounds", "persistence"))
	if len(diags) != 0 {
		t.Fatalf("expected NO diagnostics for meaningful compounds + spine types, got:\n%s", messages(diags))
	}
}

// TestCheckRejectsSpineTypeOutlier locks the founder-ruling half of check (1): the
// full-spelled spine TYPE names Configuration/Dependencies are banned AS TYPE NAMES
// (the idiomatic spine types are Config/Deps).
func TestCheckRejectsSpineTypeOutlier(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-spinetype", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected diagnostics for full-spelled spine type outliers, got none")
	}
	got := messages(diags)
	for _, want := range []string{
		`exported type "Configuration"`,
		`use Config`,
		`exported type "Dependencies"`,
		`use Deps`,
	} {
		if !strings.Contains(got, want) {
			t.Errorf("expected a diagnostic mentioning %q, got:\n%s", want, got)
		}
	}
}

// TestCheckRejectsBareConformanceEntrypoint locks check (2): a <lib>test package that
// drives a suite via a bare Run (not ^Run<Role>Suite$) is flagged.
func TestCheckRejectsBareConformanceEntrypoint(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "bad-bareentrypoint", "configuration"))
	if len(diags) == 0 {
		t.Fatal("expected a diagnostic for a bare Run conformance entrypoint, got none")
	}
	got := messages(diags)
	if !strings.Contains(got, "configurationtest") {
		t.Errorf("diagnostic should name the offending <lib>test package, got:\n%s", got)
	}
	if !strings.Contains(got, "Run<Role>Suite") {
		t.Errorf("diagnostic should name the required Run<Role>Suite shape, got:\n%s", got)
	}
}

// TestCheckAllowsSuitePlusFakeVariant is the non-vacuity guard for check (2): a
// <lib>test package exposing the primary Run<Role>Suite plus the ONE sanctioned
// Run<Role>SuiteWithFake variant is clean.
func TestCheckAllowsSuitePlusFakeVariant(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "good-suitevariant", "configuration"))
	if len(diags) != 0 {
		t.Fatalf("expected NO diagnostics for Run<Role>Suite + WithFake variant, got:\n%s", messages(diags))
	}
}

// TestCheckAllowsFixturesOnlyTestPackage guards that a <lib>test package with NO Run*
// function (a pure fixtures/helpers package — fakes, harness) makes no conformance
// claim and is NOT flagged by check (2). The existing good/configuration fixture's
// configurationtest holds only a Fake type.
func TestCheckAllowsFixturesOnlyTestPackage(t *testing.T) {
	t.Parallel()

	diags := checker.Check(fixture(t, "good", "configuration"))
	if len(diags) != 0 {
		t.Fatalf("expected a fixtures-only <lib>test package to be clean, got:\n%s", messages(diags))
	}
}

// TestExportedIdentifierTokenMatching pins the whole-identifier (never substring)
// semantics directly: bare tokens flag, compounds do not.
func TestExportedIdentifierTokenMatching(t *testing.T) {
	t.Parallel()

	// The good-compounds library is the executable assertion that ObjectStore,
	// DesiredStore, PostgresStore, TemplateStore, Author, and OAuth all pass while
	// the bad-bannedidentifier library proves the bare forms fail — covered above.
	// This test pins the precise diagnostic count for the bare fixture so a future
	// over-broad match (a compound mis-flagged) is caught as a count drift.
	diags := checker.Check(fixture(t, "bad-bannedidentifier", "identity"))
	var bareHits int
	for _, d := range diags {
		if strings.Contains(d.Message, "bare banned HNS-1 token") {
			bareHits++
		}
	}
	if bareHits != 3 {
		t.Fatalf("expected exactly 3 bare-token diagnostics (Auth, Repo, Store), got %d:\n%s", bareHits, messages(diags))
	}
}
