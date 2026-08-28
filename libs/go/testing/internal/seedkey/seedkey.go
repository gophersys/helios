// Package seedkey is the single home of the testing library's seed convention: it
// maps a uint64 seed to the [32]byte ChaCha8 key the canonical entropy engine
// (dependenciestest.Random) is constructed from.
//
// It exists so the convention has ONE definition site shared by both the core
// testing package (Runner.Fakes / the standalone Harness vend a *FakeRandomSource
// from a uint64 Seed) and the public testingtest.NewFakeRandomSource — without
// either re-rolling the derivation and without an import cycle (it is internal to
// the testing module, so both packages under it may cite it; consumers cannot).
//
// The mapping is a FROZEN invariant (contract open question 6): identical seed ⇒
// identical key ⇒ identical byte stream, forever. The exact bytes are pinned by the
// golden tests on both the testingtest fake and the Runner-vended path; changing
// this derivation is a BREAKING change that may only ship behind a new constructor.
package seedkey

import "encoding/binary"

// Derive maps a uint64 seed to the engine's 32-byte ChaCha8 key. The seed is spread
// across the four key words with the golden-ratio / mix constants so distinct seeds
// diverge immediately while the seed→key mapping stays a pure, version-pinned
// function.
func Derive(seed uint64) [32]byte {
	var key [32]byte
	binary.LittleEndian.PutUint64(key[0:8], seed)
	binary.LittleEndian.PutUint64(key[8:16], seed^0x9e3779b97f4a7c15)
	binary.LittleEndian.PutUint64(key[16:24], seed*0xff51afd7ed558ccd)
	binary.LittleEndian.PutUint64(key[24:32], seed*0xc4ceb9fe1a85ec53)
	return key
}
