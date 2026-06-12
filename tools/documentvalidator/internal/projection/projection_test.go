package projection

import (
	"os"
	"path/filepath"
	"testing"
)

func writeTemp(t *testing.T, name, content string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, name)
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write temp: %v", err)
	}
	return path
}

func TestProjectYAML(t *testing.T) {
	path := writeTemp(t, "doc.yaml", `meta:
  id: requirements
  type: requirements
  created: 2026-06-12
data:
  items:
    - id: REQ-0001
`)
	doc, err := Project(path)
	if err != nil {
		t.Fatalf("project yaml: %v", err)
	}
	if doc.DocumentType != "requirements" {
		t.Errorf("type = %q, want requirements", doc.DocumentType)
	}
	meta := doc.Projection["meta"].(map[string]any)
	// The unquoted ISO date must project to a string, not a time.Time, so the
	// JSON Schema validator sees jsonType string.
	if got, ok := meta["created"].(string); !ok || got != "2026-06-12" {
		t.Errorf("created = %#v, want string \"2026-06-12\"", meta["created"])
	}
}

func TestProjectMarkdownSections(t *testing.T) {
	path := writeTemp(t, "doc.md", `---
meta:
  id: product-charter
  type: product-charter
data:
  personas: []
---

## Vision

The vision text.

## Success Criteria

- one
- two

### A subheading stays in the body

still success criteria
`)
	doc, err := Project(path)
	if err != nil {
		t.Fatalf("project md: %v", err)
	}
	if doc.DocumentType != "product-charter" {
		t.Errorf("type = %q", doc.DocumentType)
	}
	sections, ok := doc.Projection["sections"].(map[string]any)
	if !ok {
		t.Fatalf("sections missing: %#v", doc.Projection)
	}
	if _, ok := sections["vision"]; !ok {
		t.Errorf("missing kebab-cased 'vision' section: %v", sectionKeys(sections))
	}
	sc, ok := sections["success-criteria"].(string)
	if !ok {
		t.Fatalf("missing 'success-criteria' section: %v", sectionKeys(sections))
	}
	// The ### subheading is body content, not a new section boundary.
	if _, ok := sections["a-subheading-stays-in-the-body"]; ok {
		t.Errorf("### heading was wrongly treated as a section boundary")
	}
	if want := "still success criteria"; !contains(sc, want) {
		t.Errorf("success-criteria body lost ### content: %q", sc)
	}
}

func TestProjectMarkdownMissingFrontmatter(t *testing.T) {
	path := writeTemp(t, "doc.md", "# No frontmatter here\n\nbody\n")
	if _, err := Project(path); err == nil {
		t.Fatal("expected error for markdown without frontmatter")
	}
}

func TestKebabCase(t *testing.T) {
	cases := map[string]string{
		"Vision":             "vision",
		"Success Criteria":   "success-criteria",
		"Audience and Tone":  "audience-and-tone",
		"  Padded  Heading ": "padded-heading",
		"Non-Goals":          "non-goals",
	}
	for in, want := range cases {
		if got := kebabCase(in); got != want {
			t.Errorf("kebabCase(%q) = %q, want %q", in, got, want)
		}
	}
}

func sectionKeys(m map[string]any) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	return keys
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

func TestSniffDiscriminatesNonDocuments(t *testing.T) {
	cases := []struct {
		name string
		path string
		raw  string
		want bool
	}{
		{"markdown with frontmatter", "doc.md", "---\nmeta:\n  type: requirements\n---\nbody", true},
		{"markdown without frontmatter (README)", "README.md", "# readme\n\nprose only", false},
		{"yaml with meta mapping", "doc.yaml", "meta:\n  type: requirements\ndata: {}\n", true},
		{"yaml without meta (fixture)", "values.yaml", "replicas: 3\nimage: nginx\n", false},
		{"yaml meta not a mapping", "odd.yaml", "meta: 4\n", false},
		{"invalid yaml", "broken.yaml", ":\n  - [", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := Sniff(c.path, []byte(c.raw)); got != c.want {
				t.Fatalf("Sniff(%s) = %v, want %v", c.path, got, c.want)
			}
		})
	}
}
