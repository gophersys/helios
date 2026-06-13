//go:build integration

package dockeradapter_test

import (
	"io"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// secretsForTest returns a fake secrets.Provider for integration wiring (no real vault).
func secretsForTest() *secretstest.Provider { return secretstest.New(nil) }

// clockForTest returns a deterministic Clock for integration wiring.
//
//nolint:ireturn // the fake Clock is the dependencies.Clock port the Deps hexagon takes; returning the port is the injection shape.
func clockForTest() dependencies.Clock {
	set, _, _, _ := dependenciestest.Fakes()
	return set.Clock
}

// readAll drains and closes rc.
func readAll(rc io.ReadCloser) ([]byte, error) {
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-read stream has no actionable error.
	return io.ReadAll(rc)
}
