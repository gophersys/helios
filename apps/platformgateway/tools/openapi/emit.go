package main

import (
	"fmt"
	"sort"
	"strings"
)

// header is the contract preamble the emitter writes: it states the contract is GENERATED (go-first
// -emit), so a reader edits the route types + re-emits, never hand-edits the YAML. It mirrors the
// info/servers/security block the template shipped.
const header = `# platformgateway OpenAPI contract — GENERATED, DO NOT EDIT BY HAND (ADR-0023; OD-16-openapi=go-first-emit).
#
# This file is EMITTED from the five-file route packages' Go Request/Response types by
# tools/openapi (` + "`bash ./ctl.sh openapi`" + `). The Go routes are the authoring surface; this YAML
# is their projection — edit a route's types and re-emit, never edit here. ` + "`bash ./ctl.sh" + `
# verify-openapi` + "`" + ` fails CI if this file drifts from the routes; ` + "`bash ./ctl.sh gen-client`" + ` emits
# the typed Go client from it (clients/go), which the integration lane drives through the handlers.
openapi: 3.0.3
info:
  title: platformgateway
  version: 0.1.0
  description: >-
    Eden's platformgateway — the platform HTTP API (ADR-0023). The contract is EMITTED from the Go route types
    (go-first-emit); sqlc/pgx data layer; the 5-files-per-route handler pipeline; behind the
    edenhttp dev-JWT identity gate.
servers:
  - url: /v1
    description: The versioned API surface (mounted behind the authentication Middleware).
security:
  - bearerAuth: []
`

// emit renders the full OpenAPI document for the operation registry: it walks the operations
// (grouping by path), reflects each operation's request/response types into the components map, and
// writes deterministic YAML. The output is byte-stable across re-emits with no source change (paths
// are emitted in first-seen order, components sorted), so verify-openapi can diff it.
func emit(ops []operation) string {
	components := map[string]schema{}
	var builder strings.Builder
	builder.WriteString(header)

	builder.WriteString("paths:\n")
	for _, group := range groupByPath(ops) {
		builder.WriteString("  " + group.path + ":\n")
		for i := range group.ops {
			writeOperation(&builder, &group.ops[i], components)
		}
	}

	writeComponents(&builder, components)
	return builder.String()
}

// pathGroup is the operations sharing one templated path, in declaration order.
type pathGroup struct {
	path string
	ops  []operation
}

// groupByPath buckets the operations by path, preserving first-seen path order (deterministic) and
// the declaration order within a path.
func groupByPath(ops []operation) []pathGroup {
	order := []string{}
	byPath := map[string][]operation{}
	for i := range ops {
		path := ops[i].path
		if _, seen := byPath[path]; !seen {
			order = append(order, path)
		}
		byPath[path] = append(byPath[path], ops[i])
	}
	groups := make([]pathGroup, 0, len(order))
	for _, p := range order {
		groups = append(groups, pathGroup{path: p, ops: byPath[p]})
	}
	return groups
}

// writeOperation renders one method's operation object: the operationId/summary/description, the
// path+query parameters, the request body (when the route has one), and the success + auth-failure
// responses (the success wraps the payload in the data Envelope; 401/403 document the auth gate; a
// route with a path id documents 404).
func writeOperation(b *strings.Builder, op *operation, components map[string]schema) {
	method := strings.ToLower(op.method)
	fmt.Fprintf(b, "    %s:\n", method)
	fmt.Fprintf(b, "      operationId: %s\n", op.operationID)
	fmt.Fprintf(b, "      summary: %s\n", yamlString(op.summary))
	fmt.Fprintf(b, "      description: %s\n", yamlString(op.description))

	writeParameters(b, op)
	writeRequestBody(b, op, components)
	writeResponses(b, op, components)
}

// writeParameters renders the path + query parameters (omitted when the route has none).
func writeParameters(b *strings.Builder, op *operation) {
	if len(op.pathParams) == 0 && len(op.queryParams) == 0 {
		return
	}
	b.WriteString("      parameters:\n")
	for i := range op.pathParams {
		writeParameter(b, "path", &op.pathParams[i])
	}
	for i := range op.queryParams {
		writeParameter(b, "query", &op.queryParams[i])
	}
}

// writeParameter renders one parameter object (in/name/required/description/schema).
func writeParameter(b *strings.Builder, in string, p *parameter) {
	fmt.Fprintf(b, "        - in: %s\n", in)
	fmt.Fprintf(b, "          name: %s\n", p.name)
	fmt.Fprintf(b, "          required: %t\n", p.required)
	fmt.Fprintf(b, "          description: %s\n", yamlString(p.description))
	fmt.Fprintf(b, "          schema:\n            type: %s\n", p.schemaType)
}

// writeRequestBody renders the JSON request body (the route's reflected Request schema), required,
// when the route carries a body (POST/PUT). A route with no body (GET/DELETE) emits nothing.
func writeRequestBody(b *strings.Builder, op *operation, components map[string]schema) {
	if op.requestType == nil {
		return
	}
	bodySchema := schemaForType(op.requestType, components)
	b.WriteString("      requestBody:\n        required: true\n        content:\n          application/json:\n            schema:\n")
	writeSchemaInline(b, &bodySchema, "              ")
}

// writeResponses renders the response objects: the success status (payload wrapped in the data
// Envelope), 401 (unauthenticated) and 403 (missing grant) for every authenticated route, and 404
// for a route that addresses a resource by path id.
func writeResponses(b *strings.Builder, op *operation, components map[string]schema) {
	b.WriteString("      responses:\n")
	envelope := envelopeSchema(op.responseType, components)
	fmt.Fprintf(b, "        \"%d\":\n", op.successStatus)
	b.WriteString("          description: Success.\n          content:\n            application/json:\n              schema:\n")
	writeSchemaInline(b, &envelope, "                ")
	b.WriteString("        \"401\":\n          description: Missing or invalid bearer token (the gateway is behind auth even locally).\n")
	fmt.Fprintf(b, "        \"403\":\n          description: The caller does not hold the `%s` grant.\n", op.grant)
	if len(op.pathParams) > 0 {
		b.WriteString("        \"404\":\n          description: The resource does not exist.\n")
	}
}

// writeComponents renders the components block: the securityScheme (bearer JWT) and every schema the
// operations referenced, in sorted (deterministic) order.
func writeComponents(b *strings.Builder, components map[string]schema) {
	b.WriteString("components:\n")
	b.WriteString("  securitySchemes:\n    bearerAuth:\n      type: http\n      scheme: bearer\n      bearerFormat: JWT\n")
	b.WriteString("  schemas:\n")
	for _, name := range sortedComponentNames(components) {
		fmt.Fprintf(b, "    %s:\n", name)
		component := components[name]
		writeSchemaBlock(b, &component, "      ")
	}
}

// writeSchemaInline renders a schema as a $ref (the common case for a named component) or, for a
// scalar/array, its inline type — at the given indent. Operation bodies reference components by $ref.
func writeSchemaInline(b *strings.Builder, s *schema, indent string) {
	if s.ref != "" {
		fmt.Fprintf(b, "%s$ref: %q\n", indent, s.ref)
		return
	}
	writeSchemaBlock(b, s, indent)
}

// writeSchemaBlock renders a schema's body (type/format/description/properties/required/items/$ref)
// at the given indent. It is the component renderer; it is deterministic (properties in declaration
// order, required sorted).
func writeSchemaBlock(b *strings.Builder, s *schema, indent string) {
	if s.ref != "" {
		fmt.Fprintf(b, "%s$ref: %q\n", indent, s.ref)
		return
	}
	if s.typ != "" {
		fmt.Fprintf(b, "%stype: %s\n", indent, s.typ)
	}
	if s.format != "" {
		fmt.Fprintf(b, "%sformat: %s\n", indent, s.format)
	}
	if s.description != "" {
		fmt.Fprintf(b, "%sdescription: %s\n", indent, yamlString(s.description))
	}
	if s.items != nil {
		fmt.Fprintf(b, "%sitems:\n", indent)
		writeSchemaBlock(b, s.items, indent+"  ")
	}
	if len(s.required) > 0 {
		required := append([]string(nil), s.required...)
		sort.Strings(required)
		fmt.Fprintf(b, "%srequired: [%s]\n", indent, strings.Join(required, ", "))
	}
	if len(s.properties) > 0 {
		fmt.Fprintf(b, "%sproperties:\n", indent)
		for i := range s.properties {
			prop := &s.properties[i]
			fmt.Fprintf(b, "%s  %s:\n", indent, prop.name)
			writeSchemaBlock(b, &prop.schema, indent+"    ")
		}
	}
}

// yamlString renders a string as a safe single-line YAML double-quoted scalar (escaping quotes and
// backslashes), so a summary with a colon or a backtick is emitted verbatim without breaking the
// document.
func yamlString(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	s = strings.ReplaceAll(s, `"`, `\"`)
	return `"` + s + `"`
}
