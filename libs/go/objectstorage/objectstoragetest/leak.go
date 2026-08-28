package objectstoragetest

import "strings"

// TestingT is the minimal testing surface AssertNoCredentialLeak needs (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}

// AssertNoCredentialLeak fails t if credential appears verbatim in a surfaced artifact (a presigned
// URL, an error message, an ObjectInfo rendering, a captured log) — giving the credential-redaction
// guarantee a runnable assertion. credential is the EXACT value the store under test was seeded
// with (the suite threads it as a parameter — the fake binding's SeededCredentialCanary, the real
// binding's container secret key), so the needle is never stale: it always matches the credential
// the system actually resolved. An empty credential is a no-op (nothing to leak).
func AssertNoCredentialLeak(t TestingT, surface, rendered, credential string) {
	t.Helper()
	if credential != "" && strings.Contains(rendered, credential) {
		t.Errorf("credential leaked through %s: %q", surface, rendered)
	}
}
