//go:build integration

// Package vaultadapter_test's integration suite runs against a REAL HashiCorp Vault — the OFFICIAL
// hashicorp/vault container, booted in SERVER mode with file storage and a one-shot init/unseal
// bootstrap (NOT -dev in-memory mode, and NOT a bespoke self-unsealing image), per ADR-0022
// decision #1 (Mateo: "i want the real thing"). It is gated behind the `integration` build tag so
// the default `go test` (and the pre-commit hook) stays fast; run it with
//
//	go test -tags integration ./...
//
// The container is reaped on t.Cleanup (on failure too) under a unique per-test name, so parallel
// or abandoned runs never leak. The adapter resolves through its REAL vault/api transport — never a
// mock (ADR-0016 §2). docker-out-of-docker: the devcontainer reaches the sibling Vault container by
// its docker-bridge IP (docker inspect), so no published port is needed.
package vaultadapter_test

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"
)

// vaultImage is the OFFICIAL image (ADR-0022 #1). It is pre-pulled in the devcontainer.
const vaultImage = "hashicorp/vault:1.18"

// integrationCanary is the value written into the REAL Vault and resolved back through the adapter.
// It is high-entropy + self-labeling so the no-leak assertion's needle is unambiguous.
const integrationCanary = "ghp-REAL-VAULT-roundtrip-9c0ffee-d34db33f-do-not-leak"

// realVault is a booted, unsealed, configured Vault container the adapter resolves against.
type realVault struct {
	name      string
	address   string // http://<bridge-ip>:8200, reachable from the devcontainer
	username  string
	password  string
	userToken string // a userpass-minted token (for ModeTokenFile)
}

// TestIntegration_RealVaultUserpassRoundTrip is the load-bearing real-Vault proof: it boots a real
// Vault, writes a KV v2 secret holding the canary under a least-privilege userpass identity, and
// resolves it through the adapter's ModeUserpass path (env-less userpass → token → KV read → mint).
// It asserts (1) the value round-trips byte-for-byte through Use, and (2) the canary appears in NO
// surfaced artifact of the resolved Secret. No mock anywhere on this path.
//
//nolint:paralleltest // boots a real container; serial by design so the bridge-IP/bootstrap is deterministic.
func TestIntegration_RealVaultUserpassRoundTrip(t *testing.T) {
	requireDocker(t)
	v := startRealVault(t)

	adapter, err := vaultadapter.New(
		vaultadapter.Config{Address: v.address, Mode: vaultadapter.ModeUserpass},
		vaultadapter.Dependencies{Username: v.username, Password: v.password},
	)
	if err != nil {
		t.Fatalf("vaultadapter.New(ModeUserpass) against real Vault: %v", err)
	}

	ref := secrets.Ref("vault://eden/connectors/github#token")
	sec, err := adapter.Resolve(context.Background(), ref)
	if err != nil {
		t.Fatalf("Resolve against real Vault: %v", err)
	}
	defer sec.Zeroize()

	// (1) The value round-trips byte-for-byte through the only read path.
	got, err := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if err != nil {
		t.Fatalf("Use1: %v", err)
	}
	if got != integrationCanary {
		t.Fatalf("real-Vault round-trip = %q, want the written canary", got)
	}

	// (2) The canary never leaks through any surfaced projection of the resolved Secret.
	assertNoLeak(t, sec)
}

// TestIntegration_RealVaultTokenFileRoundTrip proves the PRODUCTION path (ModeTokenFile): a token
// file on disk (the K8s-SA sidecar output shape, /vault/secrets/token) carries an already-minted
// Vault token the adapter reads before each Resolve. We mint that token via userpass against the
// real Vault and write it to a temp file, then resolve the same canary through the token-file mode.
//
//nolint:paralleltest // shares the real-container, serial-by-design discipline.
func TestIntegration_RealVaultTokenFileRoundTrip(t *testing.T) {
	requireDocker(t)
	v := startRealVault(t)

	tokenFile := writeTokenFile(t, v.userToken)
	adapter, err := vaultadapter.New(
		vaultadapter.Config{Address: v.address, Mode: vaultadapter.ModeTokenFile, TokenFilePath: tokenFile},
		vaultadapter.Dependencies{},
	)
	if err != nil {
		t.Fatalf("vaultadapter.New(ModeTokenFile) against real Vault: %v", err)
	}

	ref := secrets.Ref("vault://eden/connectors/github#token")
	sec, err := adapter.Resolve(context.Background(), ref)
	if err != nil {
		t.Fatalf("Resolve(ModeTokenFile) against real Vault: %v", err)
	}
	defer sec.Zeroize()

	got, err := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if err != nil {
		t.Fatalf("Use1: %v", err)
	}
	if got != integrationCanary {
		t.Fatalf("token-file round-trip = %q, want the written canary", got)
	}
	assertNoLeak(t, sec)
}

// TestIntegration_RealVaultTypedErrors proves the taxonomy holds against a REAL Vault: a missing
// secret is NotFoundError, and a path OUTSIDE the least-privilege policy is DeniedError — the real
// 404/403 from Vault mapped to the contract's typed errors, not strings.
//
//nolint:paralleltest // real container, serial by design.
func TestIntegration_RealVaultTypedErrors(t *testing.T) {
	requireDocker(t)
	v := startRealVault(t)

	adapter, err := vaultadapter.New(
		vaultadapter.Config{Address: v.address, Mode: vaultadapter.ModeUserpass},
		vaultadapter.Dependencies{Username: v.username, Password: v.password},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ctx := context.Background()

	// A well-formed reference to a secret that does not exist → NotFoundError (real Vault 404).
	if _, nerr := adapter.Resolve(ctx, secrets.Ref("vault://eden/connectors/absent#token")); !errors.IsType[secrets.NotFoundError](nerr) {
		t.Errorf("Resolve(absent) error = %v, want NotFoundError", nerr)
	}

	// A path OUTSIDE the eden/data/* policy grant → DeniedError (real Vault 403). The least-privilege
	// userpass identity has read on eden/data/* only; "other/data/*" is denied.
	if _, derr := adapter.Resolve(ctx, secrets.Ref("vault://other/forbidden#token")); !errors.IsType[secrets.DeniedError](derr) {
		t.Errorf("Resolve(out-of-policy path) error = %v, want DeniedError", derr)
	}
}

// ── real-Vault harness (official image, server mode, init/unseal bootstrap, reaped) ─────────────.

// startRealVault boots the official Vault image, initializes + unseals it, enables userpass + a KV
// v2 mount at "eden", writes a least-privilege policy + user, writes the canary secret, and mints a
// userpass token. Everything is reaped on t.Cleanup. It returns the address/credentials the adapter
// resolves against.
func startRealVault(t *testing.T) realVault {
	t.Helper()
	name := "eden-vaultadapter-it-" + sanitize(t.Name()) + "-" + randomSuffix()

	// Boot the REAL Vault server (file storage, TLS-disabled listener; NOT -dev). IPC_LOCK +
	// disable_mlock keeps it simple in the test sandbox.
	const localConfig = `{"storage":{"file":{"path":"/vault/file"}},` +
		`"listener":[{"tcp":{"address":"0.0.0.0:8200","tls_disable":true}}],"disable_mlock":true}`
	runDocker(t, "run", "-d", "--name", name, "--cap-add=IPC_LOCK",
		"-e", "VAULT_LOCAL_CONFIG="+localConfig, vaultImage, "server")
	t.Cleanup(func() { _ = exec.Command("docker", "rm", "-f", name).Run() }) //nolint:errcheck,gosec // best-effort reap; name is a harness-generated container name, not consumer input.

	// Wait for the listener, then init/unseal.
	waitForVaultSealed(t, name)
	initJSON := dockerExec(t, name, nil, "vault", "operator", "init", "-key-shares=1", "-key-threshold=1", "-format=json")
	unsealKey := jsonField(t, initJSON, "unseal_keys_b64.0")
	rootToken := jsonField(t, initJSON, "root_token")
	dockerExec(t, name, nil, "vault", "operator", "unseal", unsealKey)

	rootEnv := []string{"VAULT_TOKEN=" + rootToken}
	dockerExec(t, name, rootEnv, "vault", "secrets", "enable", "-path=eden", "-version=2", "kv")
	dockerExec(t, name, rootEnv, "vault", "auth", "enable", "userpass")

	// Least-privilege policy: read on eden/data/* only (the path-scoped, strict-by-default isolation
	// ADR-0022 #1 describes). Write the policy file inside the container, then load it.
	const policy = `path "eden/data/*" { capabilities = ["read"] }`
	dockerExecStdin(t, name, rootEnv, policy, "sh", "-c", "cat > /tmp/eden-reader.hcl")
	dockerExec(t, name, rootEnv, "vault", "policy", "write", "eden-reader", "/tmp/eden-reader.hcl")

	const username, password = "edenuser", "edenpass-integration"
	dockerExec(t, name, rootEnv, "vault", "write", "auth/userpass/users/"+username,
		"password="+password, "policies=eden-reader")

	// Write the canary secret into KV v2.
	dockerExec(t, name, rootEnv, "vault", "kv", "put", "eden/connectors/github", "token="+integrationCanary)

	// Mint a userpass token (for the ModeTokenFile test).
	loginJSON := dockerExec(t, name, nil, "vault", "login", "-method=userpass",
		"username="+username, "password="+password, "-format=json")
	userToken := jsonField(t, loginJSON, "auth.client_token")

	ip := bridgeIP(t, name)
	address := "http://" + ip + ":8200"
	waitForVaultReady(t, address)

	return realVault{name: name, address: address, username: username, password: password, userToken: userToken}
}

// ── small docker/exec/json helpers (a test harness driving the docker + vault CLIs) ─────────────.

// requireDocker fails (not skips) when docker is absent — in the devcontainer it is guaranteed
// present, so absence is a gate FAILURE, not a skip (ADR-0020 FAIL-NOT-SKIP). The ctl integration
// verb already require_cmd's docker, so this is the in-test belt-and-suspenders.
func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Fatalf("docker not on PATH — the integration lane requires a real docker daemon (ADR-0020 FAIL-NOT-SKIP): %v", err)
	}
}

// runDocker runs `docker <args...>` and fails the test on a non-zero exit, surfacing stderr.
func runDocker(t *testing.T, args ...string) string {
	t.Helper()
	cmd := exec.Command("docker", args...) // #nosec G204 -- harness driving the docker CLI; args are fixed test literals, never consumer input.
	var out, errb bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errb
	if err := cmd.Run(); err != nil {
		t.Fatalf("docker %s: %v\nstderr: %s", strings.Join(args, " "), err, errb.String())
	}
	return out.String()
}

// dockerExec runs `docker exec [-e VAULT_ADDR ...] <name> <cmd...>` and returns stdout.
func dockerExec(t *testing.T, name string, env []string, cmd ...string) string {
	t.Helper()
	args := []string{"exec", "-e", "VAULT_ADDR=http://127.0.0.1:8200"}
	for _, e := range env {
		args = append(args, "-e", e)
	}
	args = append(args, name)
	args = append(args, cmd...)
	return runDocker(t, args...)
}

// dockerExecStdin runs a `docker exec -i` piping stdin into the container command.
func dockerExecStdin(t *testing.T, name string, env []string, stdin string, cmd ...string) {
	t.Helper()
	args := []string{"exec", "-i", "-e", "VAULT_ADDR=http://127.0.0.1:8200"}
	for _, e := range env {
		args = append(args, "-e", e)
	}
	args = append(args, name)
	args = append(args, cmd...)
	c := exec.Command("docker", args...) // #nosec G204 -- harness driving docker exec; args are fixed literals.
	c.Stdin = strings.NewReader(stdin)
	var errb bytes.Buffer
	c.Stderr = &errb
	if err := c.Run(); err != nil {
		t.Fatalf("docker exec -i %s: %v\nstderr: %s", strings.Join(cmd, " "), err, errb.String())
	}
}

// bridgeIP returns the container's docker-bridge IP, the address the devcontainer dials.
func bridgeIP(t *testing.T, name string) string {
	t.Helper()
	out := runDocker(t, "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name)
	ip := strings.TrimSpace(out)
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	return ip
}

// waitForVaultSealed polls `vault status` inside the container until the server answers (sealed +
// uninitialized is the expected pre-init state).
func waitForVaultSealed(t *testing.T, name string) {
	t.Helper()
	deadline := time.Now().Add(60 * time.Second)
	for time.Now().Before(deadline) {
		cmd := exec.Command("docker", "exec", "-e", "VAULT_ADDR=http://127.0.0.1:8200", name, "vault", "status") // #nosec G204 -- fixed harness literals.
		// vault status exits non-zero when sealed; we inspect the OUTPUT, not the exit code.
		out, _ := cmd.CombinedOutput() //nolint:errcheck // non-zero exit is the sealed state we are polling for; output is the signal.
		if strings.Contains(string(out), "Sealed") {
			return
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatal("real Vault did not reach a queryable (sealed) state within the deadline")
}

// waitForVaultReady polls the unsealed Vault's health endpoint over HTTP from the devcontainer
// until it is initialized + unsealed, so the adapter's first Resolve does not race the boot.
func waitForVaultReady(t *testing.T, address string) {
	t.Helper()
	deadline := time.Now().Add(60 * time.Second)
	for time.Now().Before(deadline) {
		cmd := exec.Command("curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", //nolint:gosec // fixed health URL, harness-internal.
			address+"/v1/sys/health")
		out, _ := cmd.CombinedOutput() //nolint:errcheck // a not-yet-ready Vault returns a non-200/refused; the HTTP code in stdout is the signal.
		if strings.TrimSpace(string(out)) == "200" {
			return
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatalf("real Vault at %s did not become healthy within the deadline", address)
}

// writeTokenFile writes token to a temp file (the K8s-SA sidecar /vault/secrets/token shape) and
// returns its path. t.TempDir reaps it.
func writeTokenFile(t *testing.T, token string) string {
	t.Helper()
	path := t.TempDir() + "/token"
	if err := os.WriteFile(path, []byte(token+"\n"), 0o600); err != nil {
		t.Fatalf("writing token file: %v", err)
	}
	return path
}

// assertNoLeak fails t if the canary appears in any surfaced projection of the resolved Secret.
func assertNoLeak(t *testing.T, sec *secrets.Secret) {
	t.Helper()
	for name, rendered := range vaultRedactionSurfaces(t, sec) {
		if strings.Contains(rendered, integrationCanary) {
			t.Fatalf("REAL-Vault canary leaked through %s: %q", name, rendered)
		}
	}
}

// jsonField extracts a dotted path from a JSON document. The path segments are field names (and
// numeric indices for arrays), e.g. the auth-token field of a login response or the first unseal key.
func jsonField(t *testing.T, doc, path string) string {
	t.Helper()
	var root any
	if err := json.Unmarshal([]byte(doc), &root); err != nil {
		t.Fatalf("parsing JSON for field %q: %v\ndoc: %s", path, err, doc)
	}
	cur := root
	for _, seg := range strings.Split(path, ".") {
		switch node := cur.(type) {
		case map[string]any:
			cur = node[seg]
		case []any:
			idx := int(seg[0] - '0')
			if idx < 0 || idx >= len(node) {
				t.Fatalf("index %q out of range for field path %q", seg, path)
			}
			cur = node[idx]
		default:
			t.Fatalf("field path %q does not resolve in the JSON document", path)
		}
	}
	s, ok := cur.(string)
	if !ok {
		t.Fatalf("field %q is not a string (%T)", path, cur)
	}
	return s
}

// sanitize maps a test name to a docker-safe container-name fragment.
func sanitize(name string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(name) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		} else {
			b.WriteByte('-')
		}
	}
	return b.String()
}

// randomSuffix is a short, collision-resistant suffix so parallel/abandoned runs never share a
// container name. It uses the nanosecond clock — sufficient for serial integration runs.
func randomSuffix() string {
	return strings.TrimPrefix(time.Now().Format("150405.000000000"), "")
}
