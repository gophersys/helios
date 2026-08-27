//go:build integration

package configuration_test

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/configuration"
)

// configuration has no docker/k3d/kind substrate (EDEN_INTEGRATION_CMDS="go"): it is a pure
// parse-time leaf. Its host-leveraging substrate (ADR-0020 dimension (d)) is the REAL filesystem
// — the composition-root edge reads config bytes off disk. So the integration lane drives the
// SAME contract over a real os.ReadFile-backed Source against real files written to a temp dir,
// never an in-memory fake. The conformance two-binding (fake ≡ real, 08 §2) is the application
// half; this is the host-leveraging half: real I/O, real bytes, real decoders, reaped on cleanup.

// fileSource is a real-filesystem configuration.Source: Read does an actual os.ReadFile under a
// root directory. This is the production-shaped edge port the composition root injects — not a
// mock; the bytes come off the real disk.
type fileSource struct{ root string }

func (s fileSource) Read(_ context.Context, name string) ([]byte, error) {
	//nolint:wrapcheck // the conformance/integration error channel asserts on the Source's raw
	// error verbatim (the *ParseError wrapping is the lib's job, not this test port's).
	return os.ReadFile(filepath.Join(s.root, name)) //nolint:gosec // G304: name is a fixed test fixture under a t.TempDir root.
}

// TestIntegration_ParsesRealFileFromDisk parses a multi-format set of real on-disk files through
// the real os.ReadFile edge and asserts the resolved Document reads back correctly — the contract
// holds against the real host filesystem, not an in-memory map.
func TestIntegration_ParsesRealFileFromDisk(t *testing.T) {
	t.Parallel()

	dir := t.TempDir()
	write := func(name, body string) {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(body), 0o600); err != nil {
			t.Fatalf("write %s: %v", name, err)
		}
	}
	write("app.json", `{"engine":{"models":[{"name":"a"}]},"port":8080}`)
	write("app.yaml", "engine:\n  region: us-east\nport: 9090\n")
	write("app.env", "TOKEN=abc\nNESTED.KEY=42\n")

	cases := []struct {
		name   string
		format configuration.Format
		path   configuration.Path
		want   string
	}{
		{"app.json", configuration.FormatJSON, "engine.models[0].name", "a"},
		{"app.yaml", configuration.FormatYAML, "engine.region", "us-east"},
		{"app.env", configuration.FormatEnv, "TOKEN", "abc"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			assertRealFileLeaf(t, dir, tc.name, tc.format, tc.path, tc.want)
		})
	}
}

// assertRealFileLeaf parses one real on-disk file via the os.ReadFile edge and asserts a leaf reads
// back as want (extracted to keep the table body under the cognitive-complexity floor).
func assertRealFileLeaf(t *testing.T, dir, name string, format configuration.Format, path configuration.Path, want string) {
	t.Helper()
	p, err := configuration.New(
		configuration.Config{Format: format},
		configuration.Deps{Source: fileSource{root: dir}},
	)
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, diags, perr := p.Parse(context.Background(), name)
	if perr != nil {
		t.Fatalf("Parse real file I/O err = %v, want nil", perr)
	}
	if diags.HasError() {
		t.Fatalf("clean real file %s produced errors: %v", name, diags.All())
	}
	v, ok := doc.Lookup(path)
	if !ok {
		t.Fatalf("Lookup(%q) missed in real-file parse", path)
	}
	got, d := v.String()
	if d != nil {
		t.Fatalf("Lookup(%q) String() diagnostic = %v", path, d)
	}
	if got != want {
		t.Fatalf("real-file %s %q = %q, want %q", name, path, got, want)
	}
}

// TestIntegration_MissingRealFileSurfacesParseError asserts the real-I/O error channel: a missing
// file on the real filesystem surfaces a *ParseError that Unwraps to the OS error (os.IsNotExist
// reachable), proving the couldn't-read discipline holds against the host, not a staged map.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; runs serially so a parallel sibling cannot perturb the orphan-goroutine assertion.
func TestIntegration_MissingRealFileSurfacesParseError(t *testing.T) {
	defer goleak.VerifyNone(t)

	dir := t.TempDir()
	p, err := configuration.New(
		configuration.Config{Format: configuration.FormatJSON},
		configuration.Deps{Source: fileSource{root: dir}},
	)
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, _, perr := p.Parse(context.Background(), "does-not-exist.json")
	if perr == nil {
		t.Fatal("missing real file must surface a *ParseError")
	}
	var pe *configuration.ParseError
	if !errors.As(perr, &pe) {
		t.Fatalf("missing-file err = %T, want *ParseError", perr)
	}
	if !os.IsNotExist(pe.Unwrap()) {
		t.Fatalf("ParseError must Unwrap to the OS not-exist error, got %v", pe.Unwrap())
	}
}
