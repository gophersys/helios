//go:build integration

// users_integration_test.go is platformgateway's REAL-substrate integration lane (ADR-0016 §2: never
// mocked). It stands up an EPHEMERAL postgres on docker, runs the EMBEDDED startup migrate path
// (dataStore.Migrate — the SAME path the composition root runs on boot), seeds the default user
// idempotently, wires the typed persistence facade through server.New, serves the assembled handler
// tree, and drives the users read slice through the EMITTED Go client (clients/go) — so the OpenAPI
// contract, the five-file routes, the sqlc data layer, the IOTEA-style migrate+seed, and the auth
// spine are proven to AGREE end to end on a real database. Every docker resource is labeled with a
// unique namespace and reaped on cleanup. Run via `bash ./ctl.sh integration` (the lane requires docker).
package server_test

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	client "github.com/gophersys/eden/apps/platformgateway/clients/go/generated"
	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
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

// TestIntegration_UsersReadSlice proves the migrate+seed boot and the users read slice on a REAL
// postgres, driven through the EMITTED client. The seed plants the default user; a re-seed is a no-op
// (idempotent); list returns exactly that one default user; get-by-id returns it; an absent id is a
// typed 404; and the routes sit behind the auth spine (401 unauthenticated, 403 wrong grant).
func TestIntegration_UsersReadSlice(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	dataStore := openPersistence(t, dsn)
	ctx := context.Background()

	// The embedded startup migrate path applies the schema (the SAME path the composition root runs),
	// then the idempotent seed plants the default user — the IOTEA-style boot, proven on real postgres.
	if err := dataStore.Migrate(ctx); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	defaultID := uuid.New()
	if err := dataStore.Users().EnsureDefault(ctx, defaultID, "default@eden.local", "Default User"); err != nil {
		t.Fatalf("seed default user: %v", err)
	}
	// A second EnsureDefault with the SAME email is a no-op (ON CONFLICT DO NOTHING): the boot seed
	// must be safe to re-run on every start without erroring or duplicating the default user.
	if err := dataStore.Users().EnsureDefault(ctx, uuid.New(), "default@eden.local", "Someone Else"); err != nil {
		t.Fatalf("re-seed default user (idempotent): %v", err)
	}

	// DB-driven authorize: the token carries only the subject, so the caller needs a REAL membership for
	// the resolver to grant them. Seed the default user as an ADMIN member (permission set {*}); admin's
	// wildcard "*" grant covers users:read, so the bearer for THIS user authorizes the read routes.
	seedRBAC(ctx, t, dataStore, defaultID, uuid.New(), uuid.New(), uuid.New())

	srv := newServerWithRealStore(t, dataStore)
	httpServer := httptest.NewServer(srv.Handler())
	t.Cleanup(httpServer.Close)

	// The bearer's SUBJECT is the seeded admin user id; the real resolver loads their {*} grant from the
	// membership, which Covers users:read — the DB-driven authorize, proven on the real database.
	bearer := tokenForSubject(t, defaultID.String())
	api, err := client.NewClientWithResponses(httpServer.URL+"/v1", client.WithRequestEditorFn(
		func(_ context.Context, request *http.Request) error {
			request.Header.Set("Authorization", "Bearer "+bearer)
			return nil
		},
	))
	if err != nil {
		t.Fatalf("new client: %v", err)
	}

	driveList(ctx, t, api, defaultID)
	driveGet(ctx, t, api, defaultID)
	driveGetNotFound(ctx, t, api)
	driveAuthorizationDenied(ctx, t, httpServer.URL, dataStore)
	driveBootstrap(t, httpServer.URL, defaultID)
}

// driveBootstrap hits the PUBLIC login bootstrap (no token, no /v1 prefix — pre-identity, like the
// health probes) and asserts it returns the seeded default user. This is the exact route the basic
// login reads on a real database.
func driveBootstrap(t *testing.T, baseURL string, wantID uuid.UUID) {
	t.Helper()
	resp, err := http.Get(baseURL + "/bootstrap/default-user") //nolint:noctx // a test probe of a local httptest server.
	if err != nil {
		t.Fatalf("bootstrap GET: %v", err)
	}
	defer func() { _ = resp.Body.Close() }() //nolint:errcheck // probe response close fault is irrelevant to the assertion.
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("bootstrap status = %d, want 200 (public, no token)", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("bootstrap read body: %v", err)
	}
	var envelope struct {
		Data struct {
			Id        string `json:"id"`
			Email     string `json:"email"`
			IsDefault bool   `json:"isDefault"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		t.Fatalf("bootstrap decode: %v; body = %s", err, string(body))
	}
	if envelope.Data.Id != wantID.String() || envelope.Data.Email != "default@eden.local" || !envelope.Data.IsDefault {
		t.Fatalf("bootstrap returned %+v, want the seeded default user (id %s)", envelope.Data, wantID)
	}
}

// driveList lists users and asserts the single seeded default user is the only row (the re-seed was a
// no-op), with its id, email, and the default flag — proving migrate+seed+list agree on real postgres.
func driveList(ctx context.Context, t *testing.T, api *client.ClientWithResponses, wantID uuid.UUID) {
	t.Helper()
	listed, err := api.ListUsersWithResponse(ctx, &client.ListUsersParams{})
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if listed.StatusCode() != http.StatusOK || listed.JSON200 == nil || len(listed.JSON200.Data.Items) != 1 {
		t.Fatalf("list status = %d, body = %s", listed.StatusCode(), string(listed.Body))
	}
	item := listed.JSON200.Data.Items[0]
	if item.Id != wantID.String() || item.Email != "default@eden.local" || !item.IsDefault {
		t.Fatalf("list returned %+v, want the seeded default user (id %s)", item, wantID)
	}
	assertSuccessEnvelope(t, "list", listed.Body)
}

// driveGet fetches the default user by id and asserts the 200 success envelope.
func driveGet(ctx context.Context, t *testing.T, api *client.ClientWithResponses, id uuid.UUID) {
	t.Helper()
	got, err := api.GetUserWithResponse(ctx, id.String())
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.StatusCode() != http.StatusOK || got.JSON200 == nil || got.JSON200.Data.Id != id.String() {
		t.Fatalf("get status = %d, body = %s", got.StatusCode(), string(got.Body))
	}
	if got.JSON200.Data.Name != "Default User" {
		t.Fatalf("get returned name %q, want Default User", got.JSON200.Data.Name)
	}
	assertSuccessEnvelope(t, "get", got.Body)
}

// driveGetNotFound asserts a fetch of an absent user id is a typed 404 with the error Envelope (the
// not-found Kind maps to 404 end to end on the real database).
func driveGetNotFound(ctx context.Context, t *testing.T, api *client.ClientWithResponses) {
	t.Helper()
	gone, err := api.GetUserWithResponse(ctx, uuid.New().String())
	if err != nil {
		t.Fatalf("get-absent: %v", err)
	}
	if gone.StatusCode() != http.StatusNotFound {
		t.Fatalf("get-absent status = %d, want 404; body = %s", gone.StatusCode(), string(gone.Body))
	}
	assertErrorEnvelope(t, "get-absent", gone.Body)
}

// driveAuthorizationDenied proves the DB-driven authorize end to end, exercised THROUGH a generated client
// against the running server: an unauthenticated client (no bearer) is 401; an authenticated client whose
// REAL membership lacks users:read is 403. The 403 case seeds a SECOND user as a plain 'member' with a
// permission set that does NOT include users:read (only ping:read) — so the resolver loads their grants
// from the database and the route's Required users:read grant is not covered. Authorization is the route's
// Required grant checked against the DB-resolved set, not the token's.
func driveAuthorizationDenied(ctx context.Context, t *testing.T, baseURL string, dataStore *persistence.Persistence) {
	t.Helper()

	// (a) No bearer at all → 401 (the spine authenticates before authorize/parse).
	anonymous, err := client.NewClientWithResponses(baseURL + "/v1")
	if err != nil {
		t.Fatalf("new anonymous client: %v", err)
	}
	unauthenticated, err := anonymous.ListUsersWithResponse(ctx, &client.ListUsersParams{})
	if err != nil {
		t.Fatalf("list (no token): %v", err)
	}
	if unauthenticated.StatusCode() != http.StatusUnauthorized {
		t.Fatalf("list (no token) status = %d, want 401; body = %s",
			unauthenticated.StatusCode(), string(unauthenticated.Body))
	}

	// (b) Authenticated but under-granted: seed a plain 'member' whose permission set is {ping:read}
	// (NOT users:read), then drive the list route with THEIR token. The resolver loads {ping:read} from
	// the real membership, which does not cover users:read → 403.
	memberID := uuid.New()
	memberOrgID := uuid.New()
	memberPermissionSetID := uuid.New()
	// A NON-default user (EnsureUser, not EnsureDefault) — the single-default index allows only one
	// is_default row, and the read-slice's default user already holds it.
	if err := dataStore.Users().EnsureUser(ctx, memberID, "member@eden.local", "Member"); err != nil {
		t.Fatalf("seed member user: %v", err)
	}
	if err := dataStore.RBAC().EnsureOrganization(ctx, memberOrgID, "MemberOrg"); err != nil {
		t.Fatalf("seed member org: %v", err)
	}
	if err := dataStore.RBAC().EnsurePermissionSet(ctx, memberPermissionSetID, memberOrgID, "ReadPing", []string{"ping:read"}); err != nil {
		t.Fatalf("seed member permission set: %v", err)
	}
	if err := dataStore.RBAC().EnsureMembership(ctx, uuid.New(), memberOrgID, memberID, memberPermissionSetID, "member"); err != nil {
		t.Fatalf("seed member membership: %v", err)
	}

	underGranted := tokenForSubject(t, memberID.String())
	scoped, err := client.NewClientWithResponses(baseURL+"/v1", client.WithRequestEditorFn(
		func(_ context.Context, request *http.Request) error {
			request.Header.Set("Authorization", "Bearer "+underGranted)
			return nil
		},
	))
	if err != nil {
		t.Fatalf("new under-granted client: %v", err)
	}
	forbidden, err := scoped.ListUsersWithResponse(ctx, &client.ListUsersParams{})
	if err != nil {
		t.Fatalf("list (wrong grant): %v", err)
	}
	if forbidden.StatusCode() != http.StatusForbidden {
		t.Fatalf("list (wrong grant) status = %d, want 403; body = %s",
			forbidden.StatusCode(), string(forbidden.Body))
	}
}

// assertSuccessEnvelope asserts a raw 2xx body is the uniform edenhttp success Envelope: `data` is
// present and the failure fields (`errors`, `kind`) are absent/empty.
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
// populated and `kind` carries the failure classification, while `data` is absent.
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
	name := "platformgateway-it-" + strings.ReplaceAll(uuid.NewString(), "-", "")[:12]
	label := "eden-platformgateway-integration=" + name

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

// newServerWithRealStore assembles the gateway with the REAL persistence facades behind/around the auth
// spine, through the same server.New the composition root calls. It wires the REAL RBAC store and CLEARS
// the fake GrantResolver, so the server derives the persistence-backed RBACGrantResolver — authorization
// is the REAL per-request membership read on the real database (the DB-driven model proven end to end),
// not a fake. The Accounts facade is wired so the public /auth/login route is mounted too.
func newServerWithRealStore(t *testing.T, dataStore *persistence.Persistence) *server.Server {
	t.Helper()
	dependencies := newDeps(t)
	dependencies.Users = dataStore.Users()
	dependencies.RBAC = dataStore.RBAC()
	dependencies.Accounts = dataStore.Accounts()
	dependencies.DefaultUser = dataStore.Users()
	dependencies.DefaultMembership = dataStore.RBAC()
	dependencies.GrantResolver = nil // derive the REAL RBACGrantResolver from the real RBAC store.
	srv, err := server.New(server.Config{JWTSecretRef: secrets.Ref(jwtSecretRef)}, dependencies)
	if err != nil {
		t.Fatalf("server.New: %v", err)
	}
	return srv
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

// requireDocker skips with a clear failure if docker is absent — but in the devcontainer it is
// present, so the lane is REQUIRED (FAIL-NOT-SKIP) there; locally an absent docker skips this lane.
func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker not available; the integration lane requires a real docker daemon")
	}
}
