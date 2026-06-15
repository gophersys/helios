package objectstoragetest

import "strings"

// TestingT is the minimal testing surface AssertNoCredentialLeak needs (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}

// AssertNoCredentialLeak fails t if the seeded credential canary appears verbatim in a surfaced
// artifact (a presigned URL, an error message, an ObjectInfo rendering, a captured log) — giving
// the credential-redaction guarantee a runnable assertion. The canary is SeededCredentialCanary.
func AssertNoCredentialLeak(t TestingT, surface, rendered string) {
	t.Helper()
	if strings.Contains(rendered, SeededCredentialCanary) {
		t.Errorf("credential canary leaked through %s: %q", surface, rendered)
	}
}
