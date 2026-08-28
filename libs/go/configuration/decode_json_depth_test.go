package configuration_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/configuration"
)

// TestJSONNestingDepthIsBounded is the regression guard for the unbounded-recursion
// DoS: the JSON decoder recurses per nesting level, and a Go stack overflow is a
// runtime FATAL that recover() cannot catch, so adversarial input still under
// MaxSourceBytes could once crash the whole process. The decoder now halts at
// maxJSONDepth and reports a SeverityError Diagnostic instead — total decode, never
// a panic. 512 levels is past the bound but far below the stack-overflow threshold,
// so this test exercises the guard safely in-process.
func TestJSONNestingDepthIsBounded(t *testing.T) {
	t.Parallel()
	const levels = 512
	body := strings.Repeat("[", levels) + strings.Repeat("]", levels)

	doc, diags := parse(t, configuration.FormatJSON, "deep.json", body)

	if !diags.HasError() {
		t.Fatalf("deeply-nested JSON: HasError() = false, want a too-deep error diagnostic")
	}
	var found bool
	for _, d := range diags.All() {
		if d.Severity == configuration.SeverityError && strings.Contains(d.Summary, "deep") {
			found = true
		}
	}
	if !found {
		t.Fatalf("deeply-nested JSON: no 'too deep' SeverityError diagnostic in %v", diags.All())
	}
	_ = doc // total decode: a document is still returned, never a crash.
}

// TestJSONModerateNestingParses confirms the bound does not reject legitimately
// nested (if unusual) configuration: nesting comfortably under maxJSONDepth decodes
// without an error diagnostic.
func TestJSONModerateNestingParses(t *testing.T) {
	t.Parallel()
	const levels = 64
	body := strings.Repeat("[", levels) + strings.Repeat("]", levels)

	_, diags := parse(t, configuration.FormatJSON, "moderate.json", body)

	if diags.HasError() {
		t.Fatalf("moderately-nested JSON (%d levels, under the bound): HasError() = true, want false: %v",
			levels, diags.All())
	}
}
