//go:build integration

package gateway_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
)

// assertNoCanary proves the seeded credential canary appears in none of the given strings
// (a response body, an SSE payload, or a log line). It is the REQ-0021 redaction proof,
// used by the integration credential-seam test.
func assertNoCanary(t *testing.T, where string, values ...string) {
	t.Helper()
	for _, value := range values {
		if strings.Contains(value, agentsessiontest.SeededCanary) {
			t.Fatalf("credential canary leaked into %s: %q", where, value)
		}
	}
}
