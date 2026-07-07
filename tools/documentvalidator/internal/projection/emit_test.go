package projection

import (
	"encoding/json"
	"strings"
	"testing"
)

// TestMarshalTopLevelOrder pins the contract: the top-level keys are emitted in
// meta, data, sections order regardless of map iteration order, with two-space
// indentation and lexicographically sorted nested keys.
func TestMarshalTopLevelOrder(t *testing.T) {
	proj := map[string]any{
		"sections": map[string]any{"zeta": "z", "alpha": "a"},
		"data":     map[string]any{"items": []any{}},
		"meta":     map[string]any{"version": 3, "id": "requirements", "type": "requirements"},
	}
	out, err := Marshal(proj)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	text := string(out)

	metaAt := strings.Index(text, `"meta"`)
	dataAt := strings.Index(text, `"data"`)
	sectionsAt := strings.Index(text, `"sections"`)
	if metaAt < 0 || metaAt >= dataAt || dataAt >= sectionsAt {
		t.Fatalf("top-level keys out of contract order (meta=%d data=%d sections=%d):\n%s",
			metaAt, dataAt, sectionsAt, text)
	}

	// Nested keys are lexicographically sorted (encoding/json default): within
	// meta, "id" precedes "type" precedes "version"; within sections, "alpha"
	// precedes "zeta".
	if idAt, typeAt := strings.Index(text, `"id"`), strings.Index(text, `"type"`); idAt > typeAt {
		t.Errorf("nested meta keys are not sorted:\n%s", text)
	}
	if alphaAt, zetaAt := strings.Index(text, `"alpha"`), strings.Index(text, `"zeta"`); alphaAt > zetaAt {
		t.Errorf("nested section keys are not sorted:\n%s", text)
	}

	// Two-space indent on the first nested line.
	if !strings.Contains(text, "{\n  \"meta\": {") {
		t.Errorf("expected two-space top-level indent:\n%s", text)
	}

	// The result must be valid JSON.
	var round any
	if err := json.Unmarshal(out, &round); err != nil {
		t.Errorf("marshal output is not valid JSON: %v", err)
	}
}

// TestMarshalOmitsAbsentTopLevelKeys checks that a registry document (no
// sections) emits just meta and data, in order.
func TestMarshalOmitsAbsentTopLevelKeys(t *testing.T) {
	proj := map[string]any{
		"data": map[string]any{"items": []any{}},
		"meta": map[string]any{"id": "requirements"},
	}
	out, err := Marshal(proj)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if strings.Contains(string(out), "sections") {
		t.Errorf("absent sections key must be omitted:\n%s", out)
	}
	if !strings.HasPrefix(string(out), "{\n  \"meta\":") {
		t.Errorf("expected meta first:\n%s", out)
	}
}

// TestMarshalAppendsUnknownTopLevelKeys checks that an unexpected top-level key
// is preserved (appended after the known ones, lexicographically) rather than
// silently dropped.
func TestMarshalAppendsUnknownTopLevelKeys(t *testing.T) {
	proj := map[string]any{
		"meta":  map[string]any{"id": "x"},
		"extra": "kept",
	}
	out, err := Marshal(proj)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if !strings.Contains(string(out), `"extra"`) {
		t.Errorf("unknown top-level key was dropped:\n%s", out)
	}
	if metaAt, extraAt := strings.Index(string(out), `"meta"`), strings.Index(string(out), `"extra"`); metaAt > extraAt {
		t.Errorf("unknown key should follow the known ones:\n%s", out)
	}
}

// TestMarshalStable checks two marshals of the same projection are byte-identical
// (map iteration order must not leak into the output).
func TestMarshalStable(t *testing.T) {
	proj := map[string]any{
		"meta":     map[string]any{"id": "x", "b": 1, "a": 2, "c": 3, "d": 4, "e": 5},
		"data":     map[string]any{"k1": "v", "k2": "v", "k3": "v"},
		"sections": map[string]any{"s1": "x", "s2": "y"},
	}
	first, err := Marshal(proj)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 50; i++ {
		again, err := Marshal(proj)
		if err != nil {
			t.Fatal(err)
		}
		if string(again) != string(first) {
			t.Fatalf("marshal is not byte-stable across runs")
		}
	}
}
