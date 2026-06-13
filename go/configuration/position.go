package configuration

import "sort"

// lineMap maps byte offsets to 1-based line/column. It is built once per source
// so each token's Position is truthful (the retry-with-diagnostics loop and
// human operators depend on real coordinates — 04 §8).
type lineMap struct {
	// lineStart[i] is the byte offset where line (i+1) begins.
	lineStart []int
}

func newLineMap(raw []byte) *lineMap {
	starts := []int{0}
	for i, b := range raw {
		if b == '\n' {
			starts = append(starts, i+1)
		}
	}
	return &lineMap{lineStart: starts}
}

// at converts a 0-based byte offset into a 1-based Position (line, column).
func (m *lineMap) at(off int64) (line, col int) {
	if off < 0 {
		return 0, 0
	}
	o := int(off)
	// Find the last lineStart <= o.
	idx := sort.Search(len(m.lineStart), func(i int) bool { return m.lineStart[i] > o })
	idx-- // last start that is <= o
	if idx < 0 {
		idx = 0
	}
	line = idx + 1
	col = o - m.lineStart[idx] + 1
	return line, col
}

// posAtOffset builds a Position for a byte offset within a source.
func posAtOffset(source string, _ []byte, lines *lineMap, off int64) Position {
	line, col := lines.at(off)
	return Position{Source: source, Line: line, Column: col}
}
