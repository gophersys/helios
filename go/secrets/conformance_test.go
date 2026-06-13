package secrets_test

import (
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// TestConformanceFake runs the exported Provider conformance suite (contract §4)
// against the canonical in-memory fake, proving the fake is a substitutable
// Provider and that the Secret type holds the redaction line.
func TestConformanceFake(t *testing.T) {
	present := secrets.Ref("present-credential")
	absent := secrets.Ref("absent-credential")
	secretstest.RunProviderSuite(t, func() secrets.Provider {
		return secretstest.New(map[string]string{
			present.String(): secretstest.SeededPlaintext,
		})
	}, present, absent)
}
