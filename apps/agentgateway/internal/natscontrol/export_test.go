package natscontrol

import "encoding/json"

// NewForTest builds an Adapter with a nil *nats.Conn for white-box UNIT tests of the marshal arm,
// which returns before the connection is ever touched. The real round trip is the integration arm's
// job (a real *nats.Conn) — see integration_test.go.
func NewForTest() *Adapter { return &Adapter{} }

// SetMarshalControl swaps the package marshal seam so a unit test can drive the marshal-fault arm
// mock-free, returning a restore function the caller defers. Test-only (export_test.go); the default
// production marshal is json.Marshal.
func SetMarshalControl(fn func(any) ([]byte, error)) (restore func()) {
	previous := marshalControl
	marshalControl = fn
	return func() { marshalControl = previous }
}

// Compile-time guard that the seam's signature matches the production default.
var _ = func() func(any) ([]byte, error) { return json.Marshal }
