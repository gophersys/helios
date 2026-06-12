package sample

import "testing"

// BenchmarkGood uses b.Loop (Go 1.24+); must not be flagged.
func BenchmarkGood(b *testing.B) {
	for b.Loop() {
		_ = 1
	}
}
