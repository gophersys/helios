//go:build integration

// resource_integration_test.go is the http-gateway's REAL-substrate integration lane (ADR-0016 §2:
// never mocked). It stands up an EPHEMERAL postgres on docker, applies the resource migration, wires
// the typed persistence facade through server.New, serves the assembled handler tree, and drives the
// FULL resource CRUD through the EMITTED Go client (clients/go) — so the OpenAPI contract, the five-
// file routes, the sqlc data layer, and the auth spine are proven to AGREE end to end on a real
// database. Every docker resource is labeled with a unique namespace and reaped on cleanup (no
// orphan container). Run via `bash ./ctl.sh integration` (the lane requires docker).
package server_test

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	client "github.com/gophersys/libs/templates/go/http-gateway/clients/go/generated"
	"github.com/gophersys/libs/templates/go/http-gateway/internal/server"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

const (
	// postgresImage is the ephemeral database image the lane stands up (already present in the
	// devcontainer). A pinned tag keeps the lane reproducible.
	postgresImage = "postgres:16-alpine"
	// dsnRef is the secrets Reference the DSN is seeded under for persistence.New — loggable; the
	// value (with the password) never rides a log.
	dsnRef = "test://gateway-postgres-dsn"
	// readyTimeout bounds the wait for the container to accept connections.
	readyTimeout = 60 * time.Second
)

// TestIntegration_ResourceCRUD drives the full create→get→list→update→delete cycle through the
// EMITTED client against the running handlers on a REAL postgres. It is the proof the contract and
// the implementation agree (a documented-but-unimplemented route would fail; an implemented-but-
// undocumented one is never reachable through this client).
func TestIntegration_ResourceCRUD(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)
	applyMigration(t, dsn)

	dataStore := openPersistence(t, dsn)
	srv := newServerWithRealStore(t, dataStore)
	httpServer := httptest.NewServer(srv.Handler())
	t.Cleanup(httpServer.Close)

	// The emitted client, bearer-authenticated with the full resource grant set via a request editor.
	bearer := token(t, "resource:create", "resource:read", "resource:update", "resource:delete")
	api, err := client.NewClientWithResponses(httpServer.URL+"/v1", client.WithRequestEditorFn(
		func(_ context.Context, request *http.Request) error {
			request.Header.Set("Authorization", "Bearer "+bearer)
			return nil
		},
	))
	if err != nil {
		t.Fatalf("new client: %v", err)
	}
	ctx := context.Background()

	id := driveCreate(ctx, t, api)
	driveGet(ctx, t, api, id)
	driveList(ctx, t, api)
	driveUpdate(ctx, t, api, id)
	driveAuthorizationDenied(ctx, t, httpServer.URL)
	driveDelete(ctx, t, api, id)
	driveGetAfterDelete(ctx, t, api, id)
}

// driveCreate posts a resource and asserts the 201 envelope; it returns the server-minted id. It
// asserts BOTH the typed payload (the oapi-codegen-decoded JSON201) and the raw envelope shape
// ({data, no errors, no kind}) so the success Envelope contract is proven on the wire, not just the
// payload field the generated client surfaces.
func driveCreate(ctx context.Context, t *testing.T, api *client.ClientWithResponses) string {
	t.Helper()
	created, err := api.CreateResourceWithResponse(ctx, client.CreateResourceJSONRequestBody{Name: "widget"})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if created.StatusCode() != http.StatusCreated || created.JSON201 == nil {
		t.Fatalf("create status = %d, body = %s", created.StatusCode(), string(created.Body))
	}
	if created.JSON201.Data.Name != "widget" || created.JSON201.Data.Id == "" {
		t.Fatalf("create returned %+v, want a minted id + name widget", created.JSON201.Data)
	}
	assertSuccessEnvelope(t, "create", created.Body)
	return created.JSON201.Data.Id
}

// driveGet fetches the resource by id and asserts the 200 success envelope (payload + {data, no
// errors, no kind}).
func driveGet(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id string) {
	t.Helper()
	got, err := api.GetResourceWithResponse(ctx, id)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.StatusCode() != http.StatusOK || got.JSON200 == nil || got.JSON200.Data.Id != id {
		t.Fatalf("get status = %d, body = %s", got.StatusCode(), string(got.Body))
	}
	assertSuccessEnvelope(t, "get", got.Body)
}

// driveList lists resources and asserts the single page.
func driveList(ctx context.Context, t *testing.T, api *client.ClientWithResponses) {
	t.Helper()
	listed, err := api.ListResourcesWithResponse(ctx, &client.ListResourcesParams{})
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if listed.StatusCode() != http.StatusOK || listed.JSON200 == nil || len(listed.JSON200.Data.Items) != 1 {
		t.Fatalf("list status = %d, body = %s", listed.StatusCode(), string(listed.Body))
	}
}

// driveUpdate renames the resource and asserts the 200 envelope carries the new name.
func driveUpdate(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id string) {
	t.Helper()
	updated, err := api.UpdateResourceWithResponse(ctx, id, client.UpdateResourceJSONRequestBody{Name: "renamed"})
	if err != nil {
		t.Fatalf("update: %v", err)
	}
	if updated.StatusCode() != http.StatusOK || updated.JSON200 == nil || updated.JSON200.Data.Name != "renamed" {
		t.Fatalf("update status = %d, body = %s", updated.StatusCode(), string(updated.Body))
	}
}

// driveDelete deletes the resource and asserts the 200 acknowledgement.
func driveDelete(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id string) {
	t.Helper()
	deleted, err := api.DeleteResourceWithResponse(ctx, id)
	if err != nil {
		t.Fatalf("delete: %v", err)
	}
	if deleted.StatusCode() != http.StatusOK {
		t.Fatalf("delete status = %d, body = %s", deleted.StatusCode(), string(deleted.Body))
	}
}

// driveGetAfterDelete asserts a fetch of the now-deleted resource is a typed 404 (the not-found Kind
// maps to 404 end to end — the resource is genuinely gone from the real database) AND that the body
// is the error Envelope ({errors populated, kind = the not-found classification}, no data) — the
// uniform envelope holds on the failure path, not only the happy path.
func driveGetAfterDelete(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id string) {
	t.Helper()
	gone, err := api.GetResourceWithResponse(ctx, id)
	if err != nil {
		t.Fatalf("get-after-delete: %v", err)
	}
	if gone.StatusCode() != http.StatusNotFound {
		t.Fatalf("get-after-delete status = %d, want 404; body = %s", gone.StatusCode(), string(gone.Body))
	}
	assertErrorEnvelope(t, "get-after-delete", gone.Body)
}

// driveAuthorizationDenied proves the resource routes sit behind the auth spine, exercised THROUGH a
// generated client against the running server (not a httptest recorder): an unauthenticated client
// (no bearer) is 401 before any route stage runs, and an authenticated-but-under-granted client (a
// token without resource:read) is 403 — authentication then the route's declarative Required grant,
// both enforced end to end over real HTTP.
func driveAuthorizationDenied(ctx context.Context, t *testing.T, baseURL string) {
	t.Helper()

	// (a) No bearer at all → 401 (the spine authenticates before authorize/parse).
	anonymous, err := client.NewClientWithResponses(baseURL + "/v1")
	if err != nil {
		t.Fatalf("new anonymous client: %v", err)
	}
	unauthenticated, err := anonymous.ListResourcesWithResponse(ctx, &client.ListResourcesParams{})
	if err != nil {
		t.Fatalf("list (no token): %v", err)
	}
	if unauthenticated.StatusCode() != http.StatusUnauthorized {
		t.Fatalf("list (no token) status = %d, want 401; body = %s",
			unauthenticated.StatusCode(), string(unauthenticated.Body))
	}

	// (b) Authenticated but holding the wrong grant (resource:create, not resource:read) → 403 on the
	// read route — authorization is the route's Required grant, checked after a valid identity.
	underGranted := token(t, "resource:create")
	scoped, err := client.NewClientWithResponses(baseURL+"/v1", client.WithRequestEditorFn(
		func(_ context.Context, request *http.Request) error {
			request.Header.Set("Authorization", "Bearer "+underGranted)
			return nil
		},
	))
	if err != nil {
		t.Fatalf("new under-granted client: %v", err)
	}
	forbidden, err := scoped.ListResourcesWithResponse(ctx, &client.ListResourcesParams{})
	if err != nil {
		t.Fatalf("list (wrong grant): %v", err)
	}
	if forbidden.StatusCode() != http.StatusForbidden {
		t.Fatalf("list (wrong grant) status = %d, want 403; body = %s",
			forbidden.StatusCode(), string(forbidden.Body))
	}
}

// assertSuccessEnvelope asserts a raw 2xx body is the uniform edenhttp success Envelope: `data` is
// present and the failure fields (`errors`, `kind`) are absent/empty. The generated client surfaces
// only the typed `Data`, so this reads the wire bytes to prove the envelope shape itself.
func assertSuccessEnvelope(t *testing.T, label string, body []byte) {
	t.Helper()
	var envelope struct {
		Data   json.RawMessage `json:"data"`
		Errors []string        `json:"errors"`
		Kind   string          `json:"kind"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		t.Fatalf("%s: decode success envelope: %v; body = %s", label, err, string(body))
	}
	if len(envelope.Data) == 0 || string(envelope.Data) == "null" {
		t.Fatalf("%s: success envelope has no data; body = %s", label, string(body))
	}
	if len(envelope.Errors) != 0 {
		t.Fatalf("%s: success envelope carries errors %v; body = %s", label, envelope.Errors, string(body))
	}
	if envelope.Kind != "" {
		t.Fatalf("%s: success envelope carries kind %q; body = %s", label, envelope.Kind, string(body))
	}
}

// assertErrorEnvelope asserts a raw error body is the uniform edenhttp error Envelope: `errors` is
// populated and `kind` carries the failure classification (the not-found Kind for a 404), while
// `data` is absent — the envelope is uniform on the failure path too.
func assertErrorEnvelope(t *testing.T, label string, body []byte) {
	t.Helper()
	var envelope struct {
		Data   json.RawMessage `json:"data"`
		Errors []string        `json:"errors"`
		Kind   string          `json:"kind"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		t.Fatalf("%s: decode error envelope: %v; body = %s", label, err, string(body))
	}
	if len(envelope.Errors) == 0 {
		t.Fatalf("%s: error envelope has no errors; body = %s", label, string(body))
	}
	if envelope.Kind == "" {
		t.Fatalf("%s: error envelope has no kind; body = %s", label, string(body))
	}
	if len(envelope.Data) != 0 && string(envelope.Data) != "null" {
		t.Fatalf("%s: error envelope carries data %s", label, string(envelope.Data))
	}
}

// startPostgres runs an ephemeral postgres container under a unique label namespace, waits until it
// accepts connections, and returns its DSN. The container is reaped on t.Cleanup (no orphan).
func startPostgres(t *testing.T) string {
	t.Helper()
	requireDocker(t)
	name := "gateway-it-" + strings.ReplaceAll(uuid.NewString(), "-", "")[:12]
	label := "eden-http-gateway-integration=" + name

	//nolint:gosec // G204: the only variable args are a test-minted uuid name/label, never external input.
	out, err := exec.Command("docker", "run", "-d", "--rm",
		"--name", name, "--label", label,
		"-e", "POSTGRES_PASSWORD=postgres", "-e", "POSTGRES_DB=gateway",
		postgresImage).CombinedOutput()
	if err != nil {
		t.Fatalf("docker run postgres: %v: %s", err, out)
	}
	t.Cleanup(func() {
		//nolint:gosec // G204: `name` is a test-minted uuid, never external input.
		if reapOut, reapErr := exec.Command("docker", "rm", "-f", name).CombinedOutput(); reapErr != nil {
			t.Logf("reap postgres %s: %v: %s", name, reapErr, reapOut)
		}
	})

	// Docker-out-of-docker: this test process runs INSIDE the devcontainer, which shares the docker
	// daemon's default bridge network with the just-started container. Reach postgres directly at its
	// container IP on 5432 — a published host port would land on the Mac host, unreachable from here.
	ip := containerIP(t, name)
	dsn := fmt.Sprintf("postgres://postgres:postgres@%s:5432/gateway?sslmode=disable", ip)
	waitReady(t, dsn)
	return dsn
}

// containerIP resolves the container's IP on the docker bridge network (reachable from the
// devcontainer, which is on the same daemon's network).
func containerIP(t *testing.T, name string) string {
	t.Helper()
	//nolint:gosec // G204: `name` is a test-minted uuid, never external input.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).Output()
	if err != nil {
		t.Fatalf("docker inspect ip: %v", err)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("container %s has no bridge IP yet", name)
	}
	return ip
}

// waitReady polls until a pgx connection + ping succeeds or the deadline elapses.
func waitReady(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.Now().Add(readyTimeout)
	for time.Now().Before(deadline) {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		conn, err := pgx.Connect(ctx, dsn)
		if err == nil {
			pingErr := conn.Ping(ctx)
			_ = conn.Close(ctx) //nolint:errcheck // a probe connection close fault is irrelevant to readiness.
			cancel()
			if pingErr == nil {
				return
			}
		} else {
			cancel()
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatalf("postgres did not become ready within %s", readyTimeout)
}

// applyMigration applies the resource migration's +goose Up section to the database, so the suite
// runs against the SAME schema the migration produces (the migration is the source of truth, not the
// sqlc schema.sql which is only the type-check shape).
func applyMigration(t *testing.T, dsn string) {
	t.Helper()
	raw, err := os.ReadFile("../../persistence/migrations/0001_create_resource.sql")
	if err != nil {
		t.Fatalf("read migration: %v", err)
	}
	up := gooseUp(string(raw))
	if up == "" {
		t.Fatal("migration has no +goose Up section")
	}
	ctx := context.Background()
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		t.Fatalf("connect for migration: %v", err)
	}
	defer func() { _ = conn.Close(ctx) }() //nolint:errcheck // migration connection close fault is irrelevant after Exec.
	if _, err := conn.Exec(ctx, up); err != nil {
		t.Fatalf("apply migration: %v", err)
	}
}

// gooseUp extracts the SQL between "-- +goose Up" and "-- +goose Down".
func gooseUp(raw string) string {
	const upMarker, downMarker = "-- +goose Up", "-- +goose Down"
	start := strings.Index(raw, upMarker)
	if start < 0 {
		return ""
	}
	body := raw[start+len(upMarker):]
	if end := strings.Index(body, downMarker); end >= 0 {
		body = body[:end]
	}
	return strings.TrimSpace(body)
}

// openPersistence builds the typed persistence facade against the real database via persistence.New
// (the same constructor the composition root calls), through a secretstest provider seeding the DSN.
func openPersistence(t *testing.T, dsn string) *persistence.Persistence {
	t.Helper()
	dataStore, err := persistence.New(
		context.Background(),
		persistence.Configuration{DSN: secrets.Ref(dsnRef)},
		persistence.Dependencies{
			Secrets:       secretstest.New(map[string]string{dsnRef: dsn}),
			Observability: newDeps(t).Observability,
		},
	)
	if err != nil {
		t.Fatalf("persistence.New: %v", err)
	}
	t.Cleanup(dataStore.Close)
	return dataStore
}

// newServerWithRealStore assembles the gateway with the REAL persistence facade wired as the
// resource store behind the auth spine, through the same server.New the composition root calls.
func newServerWithRealStore(t *testing.T, dataStore *persistence.Persistence) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Resources = dataStore.Resources()
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
}

// requireDocker skips with a clear failure if docker is absent — but in the devcontainer it is
// present, so the lane is REQUIRED (FAIL-NOT-SKIP) there; locally an absent docker skips this lane.
func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker not available; the integration lane requires a real docker daemon")
	}
}
