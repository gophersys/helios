// Command openapi is the GO-FIRST-EMIT OpenAPI generator for the http-gateway template — the
// resolution of OD-16-openapi as go-first-emit (ADR-0023, recorded in open-decisions). The five-file
// route packages are the AUTHORING SURFACE: this tool reads their exported Request/Response Go types
// (the typed shapes the handlers actually serve) and emits contract/openapi.yaml FROM them, so the
// contract can never silently drift from the code — the Go types are the single source of truth, the
// YAML is a projection. `bash ./ctl.sh openapi` writes the contract; `bash ./ctl.sh verify-openapi`
// re-emits and diffs (a drift is a gate failure); `bash ./ctl.sh gen-client` runs oapi-codegen over
// the emitted contract to produce the typed Go client the integration lane drives.
//
// One concept, one home (10 §9): the operation registry below is the ONE place the route table's
// HTTP shape (method, path, operationId, grant, success status) is declared for the spec; the route
// packages own the runtime pipeline (the same method+path+grant on their edenhttp.Handler), and this
// registry projects them to the contract. The Request/Response SCHEMAS are not duplicated — they are
// reflected from the live route types, so a field change flows into the spec automatically.
package main

import (
	"reflect"

	pingroute "github.com/gophersys/eden/apps/platformgateway/internal/api/v1/ping"
	getroute "github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/get"
	listroute "github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users/list"
)

// operation is one route projected to the OpenAPI surface. It names the route's HTTP binding (method
// + templated path + operationId), the grant the route's Required field declares (documented as the
// authz requirement), the success status, and the live Go types whose reflected JSON Schema becomes
// the request body / response payload. The PathParams/QueryParams capture the parse stage's non-body
// inputs (the path {id}, the list ?limit/?offset) so the contract documents the full request shape.
type operation struct {
	method        string
	path          string
	operationID   string
	summary       string
	description   string
	grant         string
	successStatus int
	// requestType is the JSON request body's Go type (nil → no body, e.g. a GET/DELETE).
	requestType reflect.Type
	// responseType is the success payload's Go type, wrapped in the edenhttp data Envelope by the emitter.
	responseType reflect.Type
	// pathParams are the templated path parameters ({id}); each is a required string path param.
	pathParams []parameter
	// queryParams are the optional query parameters (?limit, ?offset).
	queryParams []parameter
}

// parameter is one non-body request input (a path or query parameter): its name, whether it is
// required, and a one-line description. Path parameters are always required; query parameters are
// optional with a server-side default.
type parameter struct {
	name        string
	required    bool
	schemaType  string
	description string
}

// idPathParam is the {id} path parameter the get route uses — declared once (one home).
var idPathParam = parameter{
	name: "id", required: true, schemaType: "string",
	description: "The user id (a uuid).",
}

// operations is the registry the emitter walks to build the contract — the full route table in
// declaration order (ping, then the users read slice). It is the go-first authoring surface's
// projection to OpenAPI: each entry's method/path/grant matches the route package's edenhttp.Handler
// binding, and its request/response types are the live route types (reflected, never re-spelled). The
// pre-identity login bootstrap (GET /bootstrap/default-user) is PUBLIC and out of this authenticated
// contract, like the health probes.
func operations() []operation {
	return []operation{
		{
			method:        "GET",
			path:          "/ping",
			operationID:   "ping",
			summary:       "Authenticated round-trip probe — echoes the caller's subject and a server timestamp.",
			description:   "Requires the `ping:read` grant. Proves the authenticated request pipeline end to end (authenticate -> authorize -> execute).",
			grant:         "ping:read",
			successStatus: 200,
			responseType:  reflect.TypeOf(pingroute.Response{}),
		},
		{
			method:        "GET",
			path:          "/users",
			operationID:   "listUsers",
			summary:       "List users (paginated, oldest-first).",
			description:   "Requires the `users:read` grant. Returns a page of users with the resolved limit/offset window.",
			grant:         "users:read",
			successStatus: 200,
			responseType:  reflect.TypeOf(listroute.Response{}),
			queryParams: []parameter{
				{name: "limit", required: false, schemaType: "integer", description: "Page size (default 50, max 200)."},
				{name: "offset", required: false, schemaType: "integer", description: "Page offset (0-based)."},
			},
		},
		{
			method:        "GET",
			path:          "/users/{id}",
			operationID:   "getUser",
			summary:       "Get a user by id.",
			description:   "Requires the `users:read` grant. A missing user is a 404.",
			grant:         "users:read",
			successStatus: 200,
			responseType:  reflect.TypeOf(getroute.Response{}),
			pathParams:    []parameter{idPathParam},
		},
	}
}
