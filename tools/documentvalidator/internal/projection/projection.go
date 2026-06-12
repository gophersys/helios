// Package projection reads a project document from disk and projects it to the
// canonical JSON shape {meta, data, sections} that the schemas validate against
// (doc 11 §5: "the file is just its authoring format; a document is the
// projection").
//
// Two authoring surfaces are supported:
//
//   - .yaml — the whole file is the {meta, data} object; there are no narrative
//     sections.
//   - .md   — a YAML frontmatter block fenced by "---" markers carries
//     {meta, data}; the markdown body is split on "## " headings into
//     `sections`, keyed by the kebab-cased heading text.
//
// Both surfaces project to the same value, so downstream shape validation and
// corpus traceability never need to know which form a document was authored in.
package projection

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// Document is a single project document after projection: its source path, the
// document type read from meta.type (empty when absent or malformed), and the
// projected {meta, data, sections} value ready for schema validation.
type Document struct {
	// Path is the absolute or caller-relative path the document was read from.
	Path string
	// DocumentType is meta.type, used to select the schema. Empty when the
	// document has no readable meta.type.
	DocumentType string
	// Projection is the {meta, data, sections} value as ordinary Go maps and
	// slices (the shape the JSON Schema validator consumes).
	Projection map[string]any
}

// DocumentID returns meta.id from the projection, or "" when it is absent or not
// a string. It is the stable identifier used to sort and name projections.
func (d *Document) DocumentID() string {
	meta, ok := d.Projection["meta"].(map[string]any)
	if !ok {
		return ""
	}
	id, _ := meta["id"].(string)
	return id
}

// IsDocumentFile reports whether a path is a candidate project document by
// extension. Schema files (.schema.json) and everything else are skipped.
func IsDocumentFile(path string) bool {
	switch strings.ToLower(filepath.Ext(path)) {
	case ".yaml", ".yml", ".md":
		return true
	default:
		return false
	}
}

// Sniff reports whether raw looks like a project document at all: a .md file
// opening with a frontmatter fence, or a .yaml/.yml file whose root mapping
// carries a "meta" mapping. Files that fail the sniff are not documents
// (READMEs, intake transcripts, fixtures living beside documents) and every
// verb skips them; files that pass the sniff but fail projection or shape are
// violations — a broken document is never silently skipped.
func Sniff(path string, raw []byte) bool {
	if strings.ToLower(filepath.Ext(path)) == ".md" {
		trimmed := bytes.TrimLeft(raw, "\xef\xbb\xbf \t\r\n")
		return bytes.HasPrefix(trimmed, []byte("---"))
	}
	var root map[string]any
	if err := yaml.Unmarshal(raw, &root); err != nil {
		return false
	}
	_, ok := root["meta"].(map[string]any)
	return ok
}

// Project reads the file at path and returns its projection. A YAML parse error,
// a missing frontmatter block in a .md file, or a non-object root is returned as
// an error so the caller can surface it as an io/usage diagnostic rather than a
// schema violation.
func Project(path string) (*Document, error) {
	raw, err := os.ReadFile(path) //nolint:gosec // path comes from a directory walk the operator chose.
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	return ProjectBytes(path, raw)
}

// ProjectBytes projects already-read document bytes, choosing the authoring
// surface (.md vs .yaml) by the extension of path. It is the byte-level core of
// Project, used when a document's content comes from somewhere other than the
// working tree (e.g. `git show <ref>:<path>` for the transition check). The path
// is used only for surface selection and error context, not read from disk.
func ProjectBytes(path string, raw []byte) (*Document, error) {
	var (
		proj map[string]any
		err  error
	)
	switch strings.ToLower(filepath.Ext(path)) {
	case ".yaml", ".yml":
		proj, err = projectYAML(raw)
	case ".md":
		proj, err = projectMarkdown(raw)
	default:
		return nil, fmt.Errorf("%s: unsupported document extension", path)
	}
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}

	return &Document{
		Path:         path,
		DocumentType: documentTypeOf(proj),
		Projection:   proj,
	}, nil
}

// projectYAML treats the whole file as the {meta, data} object.
func projectYAML(raw []byte) (map[string]any, error) {
	var root any
	if err := yaml.Unmarshal(raw, &root); err != nil {
		return nil, fmt.Errorf("yaml: %w", err)
	}
	obj, ok := normalize(root).(map[string]any)
	if !ok {
		return nil, fmt.Errorf("document root is not a mapping")
	}
	return obj, nil
}

// projectMarkdown splits a .md document into its YAML frontmatter ({meta, data})
// and its body sections (keyed by kebab-cased "## " heading text).
func projectMarkdown(raw []byte) (map[string]any, error) {
	front, body, err := splitFrontmatter(raw)
	if err != nil {
		return nil, err
	}

	var root any
	if err := yaml.Unmarshal(front, &root); err != nil {
		return nil, fmt.Errorf("frontmatter yaml: %w", err)
	}
	obj, ok := normalize(root).(map[string]any)
	if !ok {
		return nil, fmt.Errorf("frontmatter is not a mapping")
	}

	sections := splitSections(body)
	if len(sections) > 0 {
		obj["sections"] = sections
	}
	return obj, nil
}

// splitFrontmatter extracts the YAML frontmatter fenced by leading "---" / "---"
// lines and returns it alongside the remaining markdown body.
func splitFrontmatter(raw []byte) (front, body []byte, err error) {
	// Normalize CRLF so the marker match is line-oriented regardless of OS.
	text := strings.ReplaceAll(string(raw), "\r\n", "\n")
	if !strings.HasPrefix(text, "---\n") && text != "---" {
		return nil, nil, fmt.Errorf("markdown document is missing its YAML frontmatter (expected a leading '---' line)")
	}
	rest := strings.TrimPrefix(text, "---\n")
	// The closing fence is a line that is exactly "---".
	idx := indexOfClosingFence(rest)
	if idx < 0 {
		return nil, nil, fmt.Errorf("markdown frontmatter is not terminated by a closing '---' line")
	}
	front = []byte(rest[:idx])
	body = []byte(rest[idx:])
	// Drop the closing fence line itself from the body.
	if nl := bytes.IndexByte(body, '\n'); nl >= 0 {
		body = body[nl+1:]
	} else {
		body = nil
	}
	return front, body, nil
}

// indexOfClosingFence returns the byte offset of the line that is exactly "---"
// (the closing frontmatter fence), or -1 if there is none.
func indexOfClosingFence(s string) int {
	offset := 0
	for _, line := range strings.SplitAfter(s, "\n") {
		if strings.TrimRight(line, "\n") == "---" {
			return offset
		}
		offset += len(line)
	}
	return -1
}

// splitSections turns a markdown body into a map of kebab-cased "## " heading
// text to the markdown content under that heading (up to the next "## ").
func splitSections(body []byte) map[string]any {
	sections := map[string]any{}
	var (
		currentKey string
		buffer     strings.Builder
	)
	flush := func() {
		if currentKey != "" {
			sections[currentKey] = strings.TrimSpace(buffer.String())
		}
		buffer.Reset()
	}
	for _, line := range strings.Split(string(body), "\n") {
		if heading, ok := levelTwoHeading(line); ok {
			flush()
			currentKey = kebabCase(heading)
			continue
		}
		if currentKey != "" {
			buffer.WriteString(line)
			buffer.WriteByte('\n')
		}
	}
	flush()
	return sections
}

// levelTwoHeading reports whether a line is a "## " heading and returns its text.
// Deeper headings ("### ") are body content, not section boundaries.
func levelTwoHeading(line string) (string, bool) {
	if !strings.HasPrefix(line, "## ") {
		return "", false
	}
	if strings.HasPrefix(line, "### ") {
		return "", false
	}
	return strings.TrimSpace(strings.TrimPrefix(line, "## ")), true
}

// kebabCase lowercases heading text and joins its words with hyphens, matching
// the stable section-id grammar (envelope: ^[a-z][a-z0-9]*(-[a-z0-9]+)*$).
func kebabCase(s string) string {
	var b strings.Builder
	prevHyphen := true // leading position: suppress a leading hyphen
	for _, r := range strings.ToLower(s) {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
			prevHyphen = false
		default:
			if !prevHyphen {
				b.WriteByte('-')
				prevHyphen = true
			}
		}
	}
	return strings.TrimRight(b.String(), "-")
}

// documentTypeOf reads meta.type from a projection, returning "" when it is
// absent or not a string.
func documentTypeOf(proj map[string]any) string {
	meta, ok := proj["meta"].(map[string]any)
	if !ok {
		return ""
	}
	t, _ := meta["type"].(string)
	return t
}

// normalize converts the YAML decoder's map[interface{}]interface{} values into
// map[string]any throughout, so the result is valid input for the JSON Schema
// validator (which expects string-keyed maps). yaml.v3 already decodes mappings
// as map[string]interface{} when the target is `any`, but nested values are
// normalized here defensively and to coerce non-string keys to strings.
func normalize(v any) any {
	switch t := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(t))
		for k, val := range t {
			out[k] = normalize(val)
		}
		return out
	case map[any]any:
		out := make(map[string]any, len(t))
		for k, val := range t {
			out[fmt.Sprintf("%v", k)] = normalize(val)
		}
		return out
	case []any:
		out := make([]any, len(t))
		for i, val := range t {
			out[i] = normalize(val)
		}
		return out
	case time.Time:
		// yaml.v3 resolves unquoted ISO-8601 scalars (e.g. an envelope `created:
		// 2026-06-12`) to time.Time. The schemas type these fields as strings
		// (envelope $defs/isoDate), so render the value back to a string the JSON
		// Schema validator sees as `string`. Date-only values keep the YYYY-MM-DD
		// form; values with a time component round-trip as RFC 3339.
		if t.Hour() == 0 && t.Minute() == 0 && t.Second() == 0 && t.Nanosecond() == 0 {
			return t.Format("2006-01-02")
		}
		return t.Format(time.RFC3339)
	default:
		return v
	}
}
