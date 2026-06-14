package configuration_test

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// errReadDenied is a static sentinel standing in for an I/O fault from a Source on the canary
// path. A package-level sentinel (rather than an inline errors.New) keeps the err113 "no dynamic
// errors" discipline intact even on this exercise path.
var errReadDenied = errors.New("read denied")

// seededCanary is the redaction needle (ADR-0020 dimension (f), generalising
// workspaceprovidertest.SeededCanary): a secret-bearing config VALUE that, once parsed into a
// Document and then surfaced through a Diagnostic or a ParseError, must appear in NO operator-
// facing artifact. configuration is redaction-safe BY CONSTRUCTION: a Diagnostic carries the
// expected/found TYPE and the source Position — never the offending value's content — so a wrong
// secret field surfaces "expected int, found string @ secrets.token:1:1", not the token itself.
const seededCanary = "SEEDED-CANARY-c29uZw-d34db33f-do-not-leak"

// TestCanary_ConversionDiagnosticNeverEchoesValue asserts that when a secret-bearing leaf is read
// through a MISMATCHED total conversion, the resulting *Diagnostic never embeds the secret value.
// The mismatch diagnostic names the wanted type and the found kind, not the bytes — so a config
// validation report is safe to log even when the offending leaf holds a credential.
func TestCanary_ConversionDiagnosticNeverEchoesValue(t *testing.T) {
	t.Parallel()

	body, err := json.Marshal(map[string]any{
		"secrets": map[string]any{"token": seededCanary},
	})
	if err != nil {
		t.Fatalf("fixture marshal failed: %v", err)
	}
	src := configurationtest.Source{Files: map[string][]byte{"app.json": body}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, _, perr := p.Parse(context.Background(), "app.json")
	if perr != nil {
		t.Fatalf("Parse I/O err = %v, want nil", perr)
	}
	v, ok := doc.Lookup("secrets.token")
	if !ok {
		t.Fatal("Lookup(secrets.token) ok == false")
	}

	// Read the secret string leaf as an int — a deliberate type mismatch that produces a
	// *Diagnostic. The diagnostic's operator-facing text must NOT contain the secret.
	_, diag := v.Int()
	if diag == nil {
		t.Fatal("Int() on a string leaf must return a *Diagnostic")
	}
	for _, surfaced := range []string{diag.Summary, diag.Detail} {
		if strings.Contains(surfaced, seededCanary) {
			t.Fatalf("canary leaked into a Diagnostic artifact: %q", surfaced)
		}
	}
	// Position is carried (truthful coordinate) but the value is not — assert the diagnostic still
	// points at the right leaf so we know it is a real, stamped finding (not an empty one that
	// trivially passes the no-leak check).
	if diag.At != v.At() {
		t.Fatalf("mismatch diagnostic At = %+v, want the leaf At %+v", diag.At, v.At())
	}
}

// TestCanary_ParseErrorNeverEchoesSourceBytes asserts the I/O-error channel is redaction-safe: a
// *ParseError carries the input NAME and the wrapped cause, never the source's secret-bearing
// bytes. A read failure on a file whose contents embed a credential must not surface that
// credential through the error string.
func TestCanary_ParseErrorNeverEchoesSourceBytes(t *testing.T) {
	t.Parallel()

	// The Source fails the read; the canary lives in the (unread) staged bytes AND in the error
	// cause's wrapped message must not be fabricated from them.
	failSrc := configurationtest.Source{
		Files: map[string][]byte{"secret.json": []byte(`{"token":"` + seededCanary + `"}`)},
		Err:   map[string]error{"secret.json": errReadDenied},
	}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: failSrc})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, _, perr := p.Parse(context.Background(), "secret.json")
	if perr == nil {
		t.Fatal("read failure must surface a *ParseError")
	}
	if strings.Contains(perr.Error(), seededCanary) {
		t.Fatalf("canary leaked through ParseError: %q", perr.Error())
	}
}

// TestCanary_OverCapDiagnosticNeverEchoesBytes asserts the MaxSourceBytes guard's over-cap
// Diagnostic reports sizes, never the truncated content: a source that overflows the cap and
// happens to contain a secret must not surface it in the cap finding.
func TestCanary_OverCapDiagnosticNeverEchoesBytes(t *testing.T) {
	t.Parallel()

	big := []byte(`{"token":"` + seededCanary + `","pad":"` + strings.Repeat("x", 64) + `"}`)
	src := configurationtest.Source{Files: map[string][]byte{"big.json": big}}
	p, err := configuration.New(
		configuration.Config{Format: configuration.FormatJSON, MaxSourceBytes: 8},
		configuration.Deps{Source: src},
	)
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, diags, perr := p.Parse(context.Background(), "big.json")
	if perr != nil {
		t.Fatalf("over-cap is a Diagnostic, not an I/O error: %v", perr)
	}
	if !diags.HasError() {
		t.Fatal("over-cap source must produce a SeverityError diagnostic")
	}
	for _, d := range diags.All() {
		if strings.Contains(d.Summary, seededCanary) || strings.Contains(d.Detail, seededCanary) {
			t.Fatalf("canary leaked through over-cap diagnostic: %q / %q", d.Summary, d.Detail)
		}
	}
}
