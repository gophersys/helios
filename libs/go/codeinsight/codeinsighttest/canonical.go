package codeinsighttest

import (
	"time"

	"github.com/gophersys/libs/go/codeinsight"
)

// The canonical conformance fixture: a small but representative history that exercises every metric
// the suite asserts. It is produced IDENTICALLY by both conformance arms — the real arm seeds it
// into an on-disk git repository and walks it with the system-git History; the fake arm writes the
// SAME source files to disk (so the native Go provider has real files to parse) and replays the SAME
// commit slice through FakeHistory. So both arms feed the analyzer identical data by construction,
// and the only thing under test that differs is the History binding (substitutability).

// simpleSource is a low-complexity Go file: it should rate HIGH on maintainability.
const simpleSource = `package fixture

// Greeting returns a fixed greeting.
func Greeting() string {
	return "hello"
}
`

// complexSource is a high-complexity Go file: deep nesting + many branches, so its per-function
// maintainability index is materially lower than simple.go (the discrimination the PoC's whole-file
// sum destroyed by saturating large files to a uniform E).
const complexSource = `package fixture

// Classify walks a deeply nested decision tree over its inputs.
func Classify(a, b, c, d int) int {
	total := 0
	for i := 0; i < a; i++ {
		if i%2 == 0 && i > 1 {
			for j := 0; j < b; j++ {
				if j > c || j < d {
					switch j {
					case 1:
						total += 1
					case 2:
						total += 2
					default:
						if j > 10 {
							total += j
						}
					}
				}
			}
		} else if i%3 == 0 {
			total -= 1
		}
	}
	return total
}
`

// hotSource is a Go file with a couple of branches that is edited repeatedly across the history — it
// becomes the top hotspot (change frequency × complexity).
const hotSource = `package fixture

// Pick selects a value by sign.
func Pick(x int) int {
	if x > 0 {
		return x
	}
	if x < 0 {
		return -x
	}
	return 0
}
`

// pairASource / pairBSource co-change in lockstep across several commits — the logical-coupling
// edge the suite asserts.
const pairASource = `package fixture

// Encode is half of a coupled pair.
func Encode(x int) int { return x + 1 }
`

const pairBSource = `package fixture

// Decode is the other half of the coupled pair.
func Decode(x int) int { return x - 1 }
`

// authorAda and authorBo are the two ownership identities (Ada owns the hot file, Bo contributes).
const (
	authorAda = "Ada Lovelace <ada@eden.dev>"
	authorBo  = "Bo Programmer <bo@eden.dev>"
)

// CanonicalSeed is the RepoSeed both conformance arms apply to an on-disk repository. The commit
// order, authors, and co-change structure are fixed so every asserted metric is reproducible.
func CanonicalSeed() RepoSeed {
	return RepoSeed{
		DefaultBranch: "main",
		Commits: []SeedCommit{
			{Files: map[string]string{"simple.go": simpleSource}, Message: "add simple", Author: authorAda},
			{Files: map[string]string{"complex.go": complexSource}, Message: "add complex", Author: authorBo},
			{Files: map[string]string{"hot.go": hotSource}, Message: "add hot", Author: authorAda},
			{Files: map[string]string{"pair_a.go": pairASource, "pair_b.go": pairBSource}, Message: "add pair", Author: authorAda},
			{Files: map[string]string{"hot.go": hotSource + "\n// edit 1\n"}, Message: "edit hot 1", Author: authorAda},
			{Files: map[string]string{"pair_a.go": pairASource + "\n// edit a\n", "pair_b.go": pairBSource + "\n// edit b\n"}, Message: "edit pair 1", Author: authorAda},
			{Files: map[string]string{"hot.go": hotSource + "\n// edit 2\n"}, Message: "edit hot 2", Author: authorBo},
			{Files: map[string]string{"pair_a.go": pairASource + "\n// edit a2\n", "pair_b.go": pairBSource + "\n// edit b2\n"}, Message: "edit pair 2", Author: authorAda},
		},
	}
}

// FakeArm builds a HistoryFactory whose History is the in-memory FakeHistory replaying the canonical
// commits, backed by the canonical source files written to a fresh on-disk repository (so the native
// Go provider has real files to parse). The HEAD is a synthesized hash. This is the hermetic
// conformance arm.
func FakeArm(t TestingT) HistoryFactory {
	t.Helper()
	return func() (codeinsight.History, string, string) {
		dir := NewRealRepo(t, CanonicalSeed())
		const head = "0000000000000000000000000000000000000000"
		return &FakeHistory{Commits: canonicalCommits(head), Head: head}, dir, head
	}
}

// RealArm builds a HistoryFactory whose History is the REAL system-git History walking the canonical
// seed in a fresh on-disk repository (never a mocked git) — the integration arm. The HEAD is read
// back from the seeded repository so the two arms feed the analyzer the same shape of data.
func RealArm(t TestingT) HistoryFactory {
	t.Helper()
	return func() (codeinsight.History, string, string) {
		dir := NewRealRepo(t, CanonicalSeed())
		return codeinsight.NewSystemGitHistory(), dir, headOf(t, dir)
	}
}

// canonicalCommits is the FakeHistory replay of the canonical seed — the SAME commits a system-git
// walk yields (newest→oldest), with line deltas matching the seed's edits. The fake arm replays
// this while the on-disk files (written by NewRealRepo) back the static-metric reads, so both arms
// feed the analyzer identical data.
func canonicalCommits(head string) []codeinsight.Commit {
	at := func(index int) string { return epoch.Add(time.Duration(index) * time.Hour).Format(time.RFC3339) }
	// newest → oldest (index 7 is the latest commit).
	return []codeinsight.Commit{
		{Hash: head, Author: authorAda, At: at(7), Changes: []codeinsight.FileChange{{Path: "pair_a.go", Added: 1}, {Path: "pair_b.go", Added: 1}}},
		{Hash: "c6", Author: authorBo, At: at(6), Changes: []codeinsight.FileChange{{Path: "hot.go", Added: 1}}},
		{Hash: "c5", Author: authorAda, At: at(5), Changes: []codeinsight.FileChange{{Path: "pair_a.go", Added: 1}, {Path: "pair_b.go", Added: 1}}},
		{Hash: "c4", Author: authorAda, At: at(4), Changes: []codeinsight.FileChange{{Path: "hot.go", Added: 1}}},
		{Hash: "c3", Author: authorAda, At: at(3), Changes: []codeinsight.FileChange{{Path: "pair_a.go", Added: 3}, {Path: "pair_b.go", Added: 3}}},
		{Hash: "c2", Author: authorAda, At: at(2), Changes: []codeinsight.FileChange{{Path: "hot.go", Added: 11}}},
		{Hash: "c1", Author: authorBo, At: at(1), Changes: []codeinsight.FileChange{{Path: "complex.go", Added: 28}}},
		{Hash: "c0", Author: authorAda, At: at(0), Changes: []codeinsight.FileChange{{Path: "simple.go", Added: 6}}},
	}
}
