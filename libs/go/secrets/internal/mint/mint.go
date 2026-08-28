// Package mint is the unexported minting seam shared by the secrets package and
// the secretstest package. It holds a single function variable that the secrets
// package populates (in its init) with the only constructor able to build a real
// *secrets.Secret from raw bytes; secretstest reads it through Hook to mint
// genuine, un-printable secrets for tests.
//
// This package knows NOTHING of the *secrets.Secret type (typing Hook as
// func([]byte) any would create an import cycle: secrets imports mint, so mint
// must not import secrets). The any return is type-asserted back to
// *secrets.Secret on the secretstest side. The seam weakens the SOURCE of bytes
// (a test can mint), never the type's redaction/zeroize invariants — and it is
// reachable only from within the module (an internal/ package), so no consumer
// can fabricate a Secret. There is no //go:linkname and no exported public
// constructor (contract §3 minting note, §6.7).
package mint

// hook is the constructor the secrets package installs in its init. It builds a
// real, un-printable *secrets.Secret (returned as any to avoid the import cycle)
// owning a private copy of plaintext.
var hook func(plaintext []byte) any

// Register is called once, from the secrets package's init, to install the
// minting constructor. It must not be called by consumers.
func Register(fn func(plaintext []byte) any) { hook = fn }

// Hook returns the installed minting constructor. It panics if called before the
// secrets package has been initialized, which cannot happen in practice because
// any importer of secretstest transitively initializes secrets first.
func Hook() func(plaintext []byte) any {
	if hook == nil {
		panic("secrets/internal/mint: minting hook not registered (import the secrets package)")
	}
	return hook
}
