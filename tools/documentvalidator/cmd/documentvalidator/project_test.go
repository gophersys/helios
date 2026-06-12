package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestProjectNDJSONStableAndSorted checks the default `project` surface: one
// compact projection per line, documents ordered by document id, top-level keys
// in the contract order (meta, data, sections).
func TestProjectNDJSONStableAndSorted(t *testing.T) {
	code, stdout, stderr := runCLI("project", exampleDir(t))
	if code != exitClean {
		t.Fatalf("project exited %d\nstderr:\n%s", code, stderr)
	}

	lines := nonEmptyLines(stdout)
	if len(lines) != 10 {
		t.Fatalf("expected 10 NDJSON lines (one per linkbox doc), got %d:\n%s", len(lines), stdout)
	}

	var ids []string
	for _, line := range lines {
		// Each line must be valid JSON and begin with the meta key (contract order).
		if !strings.HasPrefix(line, `{"meta":`) {
			t.Errorf("line does not lead with the meta key:\n%s", line)
		}
		var obj map[string]json.RawMessage
		if err := json.Unmarshal([]byte(line), &obj); err != nil {
			t.Fatalf("line is not valid JSON: %v\n%s", err, line)
		}
		var metaObj struct {
			ID string `json:"id"`
		}
		if err := json.Unmarshal(obj["meta"], &metaObj); err != nil {
			t.Fatalf("meta is not an object: %v", err)
		}
		ids = append(ids, metaObj.ID)
	}

	if !isSortedAscending(ids) {
		t.Errorf("documents are not sorted by id: %v", ids)
	}

	// Stability: a second run must be byte-identical.
	_, stdout2, _ := runCLI("project", exampleDir(t))
	if stdout != stdout2 {
		t.Error("project NDJSON output is not byte-stable across runs")
	}
}

// TestProjectOutWritesFiles checks `project --out` writes one well-named,
// pretty-printed, byte-stable file per document.
func TestProjectOutWritesFiles(t *testing.T) {
	out := t.TempDir()
	code, _, stderr := runCLI("project", exampleDir(t), "--out", out)
	if code != exitClean {
		t.Fatalf("project --out exited %d\nstderr:\n%s", code, stderr)
	}

	entries, err := os.ReadDir(out)
	if err != nil {
		t.Fatalf("read out dir: %v", err)
	}
	if len(entries) != 10 {
		t.Fatalf("expected 10 projection files, got %d", len(entries))
	}

	// Each file must be valid, indented JSON ending in a newline, leading with the
	// meta key.
	for _, e := range entries {
		if filepath.Ext(e.Name()) != ".json" {
			t.Errorf("unexpected non-json file: %s", e.Name())
			continue
		}
		content, rerr := os.ReadFile(filepath.Join(out, e.Name()))
		if rerr != nil {
			t.Fatalf("read %s: %v", e.Name(), rerr)
		}
		if !strings.HasSuffix(string(content), "}\n") {
			t.Errorf("%s does not end with a closing brace + newline", e.Name())
		}
		if !strings.HasPrefix(string(content), "{\n  \"meta\": {") {
			t.Errorf("%s does not lead with an indented meta key:\n%s", e.Name(), firstLines(string(content), 2))
		}
		var v any
		if jerr := json.Unmarshal(content, &v); jerr != nil {
			t.Errorf("%s is not valid JSON: %v", e.Name(), jerr)
		}
	}

	// Stability: writing again into a fresh dir yields identical bytes.
	out2 := t.TempDir()
	if code, _, _ := runCLI("project", exampleDir(t), "--out", out2); code != exitClean {
		t.Fatal("second project --out run failed")
	}
	for _, e := range entries {
		a, _ := os.ReadFile(filepath.Join(out, e.Name()))
		b, _ := os.ReadFile(filepath.Join(out2, e.Name()))
		if string(a) != string(b) {
			t.Errorf("%s differs between two project --out runs", e.Name())
		}
	}
}

// TestProjectMatchesGoldenViaCLI is a second pin on the contract: `project --out`
// reproduces the committed golden fixtures byte-for-byte.
func TestProjectMatchesGoldenViaCLI(t *testing.T) {
	out := t.TempDir()
	if code, _, stderr := runCLI("project", exampleDir(t), "--out", out); code != exitClean {
		t.Fatalf("project --out failed\nstderr:\n%s", stderr)
	}
	golden := goldenDir(t)
	entries, err := os.ReadDir(golden)
	if err != nil {
		t.Fatalf("read golden dir (run: go test ./... -run Golden -update): %v", err)
	}
	for _, e := range entries {
		want, _ := os.ReadFile(filepath.Join(golden, e.Name()))
		got, gerr := os.ReadFile(filepath.Join(out, e.Name()))
		if gerr != nil {
			t.Errorf("project --out did not write %s", e.Name())
			continue
		}
		if string(want) != string(got) {
			t.Errorf("%s: project --out drifted from golden", e.Name())
		}
	}
}

func nonEmptyLines(s string) []string {
	var out []string
	for _, line := range strings.Split(s, "\n") {
		if strings.TrimSpace(line) != "" {
			out = append(out, line)
		}
	}
	return out
}

func isSortedAscending(values []string) bool {
	for i := 1; i < len(values); i++ {
		if values[i-1] > values[i] {
			return false
		}
	}
	return true
}

func firstLines(s string, n int) string {
	lines := strings.Split(s, "\n")
	if len(lines) > n {
		lines = lines[:n]
	}
	return strings.Join(lines, "\n")
}
