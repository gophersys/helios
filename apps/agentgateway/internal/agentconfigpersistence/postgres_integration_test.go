//go:build integration

package agentconfigpersistence_test

import (
	"context"
	"fmt"
	"os/exec"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/gophersys/eden/apps/agentgateway/internal/agentconfigpersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// TestIntegration_PostgresAgentConfigStore proves the REAL Postgres AgentConfigStore against a REAL
// postgres:16-alpine container (no mock): upsert → get (found + not-found) → list (sorted) → re-put
// (idempotent overwrite). Mirrors the orchestrator's real-substrate posture (docker-out-of-docker,
// reaped on cleanup; SKIP without docker locally, REQUIRED in the devcontainer).
func TestIntegration_PostgresAgentConfigStore(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	configStore, err := agentconfigpersistence.NewPostgres(ctx, dsn)
	if err != nil {
		t.Fatalf("NewPostgres: %v", err)
	}
	defer configStore.Close()

	put := func(agentType, model string, grants []string) {
		if _, putErr := configStore.Put(ctx, gateway.AgentConfig{
			AgentType: agentType, Model: model, ToolGrants: grants, SandboxPosture: "strict",
		}); putErr != nil {
			t.Fatalf("Put(%s): %v", agentType, putErr)
		}
	}
	put("implementer", "claude-fable-5", []string{"Read", "Write"})
	put("architect", "claude-opus", []string{"Read"})

	// Get round-trips faithfully; a missing type is a typed KindNotFound.
	got, err := configStore.Get(ctx, "implementer")
	if err != nil {
		t.Fatalf("Get(implementer): %v", err)
	}
	if got.Model != "claude-fable-5" || !slices.Equal(got.ToolGrants, []string{"Read", "Write"}) {
		t.Fatalf("Get round-trip drift: %+v", got)
	}
	if _, missErr := configStore.Get(ctx, "supervisor"); errors.KindOf(missErr) != errors.KindNotFound {
		t.Fatalf("Get(missing) kind: got %v want KindNotFound", errors.KindOf(missErr))
	}

	// List is sorted by agent type (architect before implementer).
	configs, err := configStore.List(ctx)
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	names := make([]string, len(configs))
	for i := range configs {
		names[i] = configs[i].AgentType
	}
	if !slices.Equal(names, []string{"architect", "implementer"}) {
		t.Fatalf("List order: got %v want [architect, implementer]", names)
	}

	// Re-put overwrites (upsert on agent_type, not a duplicate row).
	put("implementer", "claude-sonnet", []string{"Read"})
	reread, err := configStore.Get(ctx, "implementer")
	if err != nil {
		t.Fatalf("Get after re-put: %v", err)
	}
	if reread.Model != "claude-sonnet" {
		t.Fatalf("re-put did not overwrite: model = %q want claude-sonnet", reread.Model)
	}
	after, err := configStore.List(ctx)
	if err != nil {
		t.Fatalf("List after re-put: %v", err)
	}
	if len(after) != 2 {
		t.Fatalf("re-put created a duplicate: %d rows want 2", len(after))
	}
}

// startPostgres boots a REAL postgres:16-alpine container docker-out-of-docker, reaped on cleanup.
func startPostgres(t *testing.T) string {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-postgres AgentConfigStore arm is skipped")
	}
	name := "eden-agentconfigpersistence-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	// #nosec G204 -- fixed `docker run` of the official postgres image; name is time-derived, not user input.
	run := exec.Command("docker", "run", "-d", "--rm", "--name", name,
		"-e", "POSTGRES_PASSWORD=eden", "-e", "POSTGRES_USER=eden", "-e", "POSTGRES_DB=eden",
		"postgres:16-alpine", "-c", "fsync=off")
	if out, err := run.CombinedOutput(); err != nil {
		t.Skipf("could not start postgres container (image unavailable?): %v\n%s", err, out)
	}
	t.Cleanup(func() {
		// #nosec G204 -- fixed `docker rm -f` of the just-created container by its time-derived name.
		_ = exec.Command("docker", "rm", "-f", name).Run() //nolint:errcheck // best-effort reap.
	})

	// #nosec G204 -- fixed `docker inspect` of the just-created container by its time-derived name.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).CombinedOutput()
	if err != nil {
		t.Fatalf("docker inspect: %v\n%s", err, out)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	dsn := fmt.Sprintf("postgres://eden:eden@%s:5432/eden?sslmode=disable", ip)
	waitForPostgres(t, dsn)
	return dsn
}

func waitForPostgres(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.After(45 * time.Second)
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		ok := pingPostgres(ctx, dsn)
		cancel()
		if ok {
			return
		}
		select {
		case <-deadline:
			t.Fatalf("postgres at %s never became ready", dsn)
		case <-time.After(300 * time.Millisecond):
		}
	}
}

func pingPostgres(ctx context.Context, dsn string) bool {
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return false
	}
	defer func() { _ = conn.Close(ctx) }() //nolint:errcheck // best-effort close of the probe conn.
	var one int
	if qerr := conn.QueryRow(ctx, "SELECT 1").Scan(&one); qerr != nil {
		return false
	}
	return one == 1
}
