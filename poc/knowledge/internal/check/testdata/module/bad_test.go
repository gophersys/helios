package sample

import "testing"

// BenchmarkBad violates go/benchmark-loop (b.N loop).
func BenchmarkBad(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = i
	}
}
