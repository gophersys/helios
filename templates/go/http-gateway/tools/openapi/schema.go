package main

import (
	"reflect"
	"sort"
	"strings"
	"time"
)

// schema is the minimal JSON Schema subset the emitter produces (OpenAPI 3.1 schemas ARE JSON
// Schema). It is an ordered map rendered to YAML; only the keywords the route types exercise are
// modeled (type, format, properties, required, items, $ref, description). Keeping it small keeps the
// projection honest — the schema mirrors the Go type, nothing more.
type schema struct {
	ref         string
	typ         string
	format      string
	description string
	properties  []property
	required    []string
	items       *schema
}

// property is one object property: its JSON name and its schema.
type property struct {
	name   string
	schema schema
}

// timeType is the reflect.Type of time.Time, mapped to a JSON string with date-time format (the
// route View timestamps are RFC3339 strings, but a reflected time.Time would otherwise be an object).
var timeType = reflect.TypeOf(time.Time{})

// schemaForType reflects a Go struct type into a JSON Schema object, recording every named component
// it references into components so the emitter can render a $ref-based document. It is the heart of
// go-first-emit: the contract's shapes come from the live route types, never a hand-kept copy. A
// json:"-" field is skipped (it is not on the wire — e.g. the path-sourced id on update.Request); a
// `,omitempty` tag drops the field from `required`.
func schemaForType(t reflect.Type, components map[string]schema) schema {
	t = deref(t)
	if t == timeType {
		return schema{typ: "string", format: "date-time"}
	}
	switch t.Kind() {
	case reflect.String:
		return schema{typ: "string"}
	case reflect.Bool:
		return schema{typ: "boolean"}
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return schema{typ: "integer", format: int32OrInt64(t)}
	case reflect.Slice:
		item := schemaForType(t.Elem(), components)
		return schema{typ: "array", items: &item}
	case reflect.Struct:
		return structSchema(t, components)
	default:
		// A type the route surface does not use; render as a permissive object rather than fail.
		return schema{typ: "object"}
	}
}

// structSchema reflects a struct into a named component schema and returns a $ref to it. Named
// components are how oapi-codegen emits stable Go types per shape, and how the contract stays
// readable. The component name is the Go type name (e.g. "Resource", "CreateRequest"); a $ref to it
// is returned so the operation bodies reference the component, not an inline blob.
func structSchema(t reflect.Type, components map[string]schema) schema {
	name := componentName(t)
	if _, seen := components[name]; !seen {
		// Reserve the name first (a placeholder) so a self-referential type does not recurse forever.
		components[name] = schema{typ: "object"}
		object := schema{typ: "object"}
		for i := range t.NumField() {
			field := t.Field(i)
			if !field.IsExported() {
				continue
			}
			jsonName, omitempty, skip := jsonField(&field)
			if skip {
				continue
			}
			object.properties = append(object.properties, property{
				name:   jsonName,
				schema: schemaForType(field.Type, components),
			})
			if !omitempty {
				object.required = append(object.required, jsonName)
			}
		}
		components[name] = object
	}
	return schema{ref: "#/components/schemas/" + name}
}

// envelopeSchema builds the edenhttp data Envelope component wrapping payload's component (the
// uniform {data, errors, kind} success shape), and returns a $ref to it. The data property is the
// payload's $ref; errors/kind are documented as the envelope's invariant fields. The component is
// named "Envelope_<Payload>" to match the template's existing convention (Envelope_PingResponse).
func envelopeSchema(payload reflect.Type, components map[string]schema) schema {
	payloadRef := schemaForType(payload, components)
	name := "Envelope_" + componentName(payload)
	if _, seen := components[name]; !seen {
		components[name] = schema{
			typ:         "object",
			description: "The uniform edenhttp success Envelope wrapping the resource payload.",
			properties: []property{
				{name: "data", schema: payloadRef},
				{name: "errors", schema: schema{typ: "array", items: &schema{typ: "string"}}},
				{name: "kind", schema: schema{typ: "string"}},
			},
			required: []string{"data"},
		}
	}
	return schema{ref: "#/components/schemas/" + name}
}

// componentName renders the OpenAPI component name for a Go struct type. It is the package-qualified
// route name folded to a stable, readable schema name: the `view.Resource` row is "Resource", and a
// route's typed input/output is "<Operation>Request"/"<Operation>Payload". The Response Go type maps
// to "<Operation>Payload" (NOT "<Operation>Response") because oapi-codegen reserves "<Operation>
// Response" for its own WithResponses parse-wrapper type — a schema named the same would collide.
// The mapping lives here (one home) so every reference agrees.
func componentName(t reflect.Type) string {
	t = deref(t)
	if strings.HasSuffix(t.PkgPath(), "/resource/view") {
		return t.Name() // the shared wire row: "Resource".
	}
	return operationPrefix(t.PkgPath()) + schemaSuffix(t.Name())
}

// operationPrefix maps a route package path to its operationId-aligned schema prefix.
func operationPrefix(pkg string) string {
	switch {
	case strings.Contains(pkg, "/resource/create"):
		return "CreateResource"
	case strings.Contains(pkg, "/resource/get"):
		return "GetResource"
	case strings.Contains(pkg, "/resource/list"):
		return "ListResources"
	case strings.Contains(pkg, "/resource/update"):
		return "UpdateResource"
	case strings.Contains(pkg, "/resource/removal"):
		return "DeleteResource" // the operationId is deleteResource; the package is `removal` (predeclared-safe).
	case strings.HasSuffix(pkg, "/ping"):
		return "Ping"
	default:
		return ""
	}
}

// schemaSuffix renames a Go type name for the schema component: a "Response" output type becomes
// "Payload" so it does not collide with oapi-codegen's reserved "<Operation>Response" wrapper; a
// "Request" input type keeps its name (oapi-codegen names the request body "<Operation>JSONBody",
// no collision).
func schemaSuffix(typeName string) string {
	if typeName == "Response" {
		return "Payload"
	}
	return typeName
}

// jsonField extracts a struct field's JSON name, omitempty flag, and skip flag from its `json` tag,
// applying the encoding/json rules (a "-" tag skips; an empty name uses the field name).
func jsonField(field *reflect.StructField) (name string, omitempty, skip bool) {
	tag := field.Tag.Get("json")
	if tag == "-" {
		return "", false, true
	}
	parts := strings.Split(tag, ",")
	name = parts[0]
	if name == "" {
		name = field.Name
	}
	for _, opt := range parts[1:] {
		if opt == "omitempty" {
			omitempty = true
		}
	}
	return name, omitempty, false
}

// deref unwraps a pointer type to its element so a *T and a T reflect to the same schema.
func deref(t reflect.Type) reflect.Type {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	return t
}

// int32OrInt64 records the integer width as the OpenAPI format hint (int32/int64), so the emitted
// client uses the right Go width for the pagination params.
func int32OrInt64(t reflect.Type) string {
	switch t.Kind() {
	case reflect.Int64, reflect.Uint64, reflect.Int, reflect.Uint:
		return "int64"
	default:
		return "int32"
	}
}

// sortedComponentNames returns the component names in a stable (sorted) order so the emitted YAML is
// deterministic — a re-emit with no source change produces byte-identical output (the verify-openapi
// drift check depends on it).
func sortedComponentNames(components map[string]schema) []string {
	names := make([]string, 0, len(components))
	for name := range components {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}
