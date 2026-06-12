package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

// compiledSchema wraps a compiled JSON Schema so the rest of the CLI does not
// depend on the jsonschema package's types directly.
type compiledSchema struct {
	schema *jsonschema.Schema
}

// shapeError is one schema-validation failure: the failing instance pointer and
// a human-readable message.
type shapeError struct {
	Pointer string
	Message string
}

// loadSchemas reads every *.schema.json in dir, registers each under its $id so
// cross-file $refs (e.g. "eden://document/v1/envelope") resolve, compiles the
// document-type schemas, and returns them keyed by document type (the meta.type
// slug, e.g. "requirements"). The envelope is registered as a resource but is
// not itself selectable by meta.type.
func loadSchemas(dir string) (map[string]*compiledSchema, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("read schema dir %s: %w", dir, err)
	}

	compiler := jsonschema.NewCompiler()

	// Register every schema document as a resource under its $id.
	type loaded struct {
		id   string
		path string
	}
	var docs []loaded
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".schema.json") {
			continue
		}
		path := filepath.Join(dir, e.Name())
		raw, rerr := os.ReadFile(path) //nolint:gosec // path under the operator-chosen schema dir.
		if rerr != nil {
			return nil, fmt.Errorf("read %s: %w", path, rerr)
		}
		var node any
		if jerr := json.Unmarshal(raw, &node); jerr != nil {
			return nil, fmt.Errorf("parse %s: %w", path, jerr)
		}
		id := schemaID(node)
		if id == "" {
			return nil, fmt.Errorf("%s: schema has no $id", path)
		}
		if aerr := compiler.AddResource(id, node); aerr != nil {
			return nil, fmt.Errorf("register %s (%s): %w", path, id, aerr)
		}
		docs = append(docs, loaded{id: id, path: path})
	}

	// Compile the document-type schemas (everything except the envelope) and key
	// them by their type slug, derived from the $id tail.
	out := map[string]*compiledSchema{}
	// Sort for deterministic compile order / error reporting.
	sort.Slice(docs, func(i, j int) bool { return docs[i].id < docs[j].id })
	for _, d := range docs {
		typeSlug := schemaTypeSlug(d.id)
		if typeSlug == "" || typeSlug == "envelope" {
			continue
		}
		s, cerr := compiler.Compile(d.id)
		if cerr != nil {
			return nil, fmt.Errorf("compile %s: %w", d.id, cerr)
		}
		out[typeSlug] = &compiledSchema{schema: s}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("no document-type schemas found in %s", dir)
	}
	return out, nil
}

// Validate runs the compiled schema against a projection and flattens the
// validation error tree into a stable, sorted list of shapeErrors.
func (c *compiledSchema) Validate(instance map[string]any) []shapeError {
	err := c.schema.Validate(instance)
	if err == nil {
		return nil
	}
	ve, ok := err.(*jsonschema.ValidationError)
	if !ok {
		return []shapeError{{Pointer: "", Message: err.Error()}}
	}
	var out []shapeError
	collectShapeErrors(ve, &out)
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Pointer != out[j].Pointer {
			return out[i].Pointer < out[j].Pointer
		}
		return out[i].Message < out[j].Message
	})
	return out
}

// collectShapeErrors walks the validation error tree, recording only leaf
// errors (those without further causes) so the output is the set of concrete
// failing keywords rather than every intermediate allOf/$ref wrapper.
func collectShapeErrors(ve *jsonschema.ValidationError, out *[]shapeError) {
	if len(ve.Causes) == 0 {
		*out = append(*out, shapeError{
			Pointer: instanceLocation(ve),
			Message: ve.Error(),
		})
		return
	}
	for _, cause := range ve.Causes {
		collectShapeErrors(cause, out)
	}
}

// instanceLocation renders the JSON-pointer-ish location of a validation error
// within the instance (e.g. "/data/items/0/priority").
func instanceLocation(ve *jsonschema.ValidationError) string {
	if len(ve.InstanceLocation) == 0 {
		return "/"
	}
	return "/" + strings.Join(ve.InstanceLocation, "/")
}

// schemaID reads the $id from a parsed schema document.
func schemaID(node any) string {
	obj, ok := node.(map[string]any)
	if !ok {
		return ""
	}
	id, _ := obj["$id"].(string)
	return id
}

// schemaTypeSlug derives the document-type slug from a schema $id of the form
// "eden://document/v1/<slug>" (the slug is the path tail).
func schemaTypeSlug(id string) string {
	idx := strings.LastIndexByte(id, '/')
	if idx < 0 {
		return ""
	}
	return id[idx+1:]
}
