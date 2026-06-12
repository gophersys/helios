package projection

import (
	"bytes"
	"encoding/json"
	"fmt"
	"sort"
)

// topLevelKeyOrder is the stable key order of the projection's top-level object
// (doc 11 §5 / ADR-0011): meta, then data, then sections. This order is the UI
// contract — every consumer (dashboards, AssistantSessions, the HTML pipeline)
// reads the projection, so its byte form must be stable across runs and across
// machines. Nested objects below the top level are emitted by encoding/json,
// which sorts map keys lexicographically and is therefore deterministic on its
// own; only the top level needs an explicit order because {data, meta, sections}
// (alphabetical) is not the contract order.
var topLevelKeyOrder = []string{"meta", "data", "sections"}

// Marshal renders the projection to its canonical, byte-stable JSON form: the
// top-level keys in topLevelKeyOrder, every nested object with lexicographically
// sorted keys (encoding/json's default), indented with two spaces and no
// trailing newline. Top-level keys that are absent from the projection are
// omitted (a registry document has no sections); unexpected top-level keys, if
// any, are appended after the known ones in lexicographic order so no data is
// silently dropped.
func Marshal(proj map[string]any) ([]byte, error) {
	var buf bytes.Buffer
	buf.WriteString("{")

	keys := orderedTopLevelKeys(proj)
	for index, key := range keys {
		// json.MarshalIndent indents every line past the first by the prefix, so a
		// top-level prefix of two spaces nests the value correctly under the
		// two-space indent we write before its key. Nested objects below get the
		// package default (lexicographically sorted keys), which is deterministic.
		valueJSON, err := json.MarshalIndent(proj[key], "  ", "  ")
		if err != nil {
			return nil, fmt.Errorf("marshal projection key %q: %w", key, err)
		}
		if index > 0 {
			buf.WriteString(",")
		}
		buf.WriteString("\n  ")
		buf.Write(mustMarshalString(key))
		buf.WriteString(": ")
		buf.Write(valueJSON)
	}

	if len(keys) > 0 {
		buf.WriteString("\n")
	}
	buf.WriteString("}")
	return buf.Bytes(), nil
}

// orderedTopLevelKeys returns the projection's present top-level keys in the
// canonical order, with any unknown keys appended in lexicographic order.
func orderedTopLevelKeys(proj map[string]any) []string {
	known := make(map[string]bool, len(topLevelKeyOrder))
	ordered := make([]string, 0, len(proj))
	for _, key := range topLevelKeyOrder {
		known[key] = true
		if _, present := proj[key]; present {
			ordered = append(ordered, key)
		}
	}
	var extra []string
	for key := range proj {
		if !known[key] {
			extra = append(extra, key)
		}
	}
	sort.Strings(extra)
	return append(ordered, extra...)
}

// mustMarshalString JSON-encodes a string key (it cannot fail for a Go string).
func mustMarshalString(s string) []byte {
	raw, _ := json.Marshal(s)
	return raw
}
