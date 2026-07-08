package servicespec

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestImageReference proves the image-tag-as-environment-contract: a local plane renders
// `<name>:local`; a production plane renders `<registry>/<name>:<tag>`.
func TestImageReference(t *testing.T) {
	t.Parallel()
	s := ServiceSpec{Name: "agentgateway", Image: "agentgateway"}

	if got := s.ImageReference(RenderTarget{Plane: PlaneLocal}); got != "agentgateway:local" {
		t.Errorf("local image = %q, want agentgateway:local", got)
	}
	prod := RenderTarget{Plane: PlaneProduction, Registry: "ghcr.io/gophersys/eden", Tag: "1.2.3"}
	if got := s.ImageReference(prod); got != "ghcr.io/gophersys/eden/agentgateway:1.2.3" {
		t.Errorf("production image = %q, want ghcr.io/gophersys/eden/agentgateway:1.2.3", got)
	}
}

// TestRenderNeverInlinesSecretValue is the secret-safety invariant for the FromSecret env mechanism:
// a render of a spec carrying a FromSecret env entry must NEVER inline a value — the production
// manifest references the Secret by name/key (valueFrom.secretKeyRef), and the local overlay uses a
// ${VAR} interpolation. Were a renderer to print the value, this catches it. (The catalog itself no
// longer uses FromSecret — the agentgateway JWT signing key moved onto a stage-scoped Vault
// reference, H8 — but the mechanism remains a supported EnvVar kind a generated app may use, so this
// exercises it directly rather than through the catalog.)
func TestRenderNeverInlinesSecretValue(t *testing.T) {
	t.Parallel()
	const sentinelValue = "SUPER-SECRET-VALUE-must-never-render"
	services := []ServiceSpec{{
		Name:  "example",
		Image: "example",
		Ports: []Port{{Name: "http", Container: 8080, Host: 8080}},
		Env: []EnvVar{
			{Name: "EXAMPLE_SECRET", FromSecret: &SecretKeyRef{SecretName: "example-secret", Key: "value"}},
			// A renderer that mistakenly read a value into a FromSecret entry would surface it:
			{Name: "PLAIN_OK", Value: "not-a-secret"},
		},
	}}

	// Production (Helm).
	for _, f := range RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t"}, services) {
		if strings.Contains(f.Content, sentinelValue) {
			t.Errorf("helm file %s inlined a secret value", f.Path)
		}
	}
	helm := joinHelm(RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t"}, services))
	if !strings.Contains(helm, "secretKeyRef") || !strings.Contains(helm, "example-secret") {
		t.Error("helm did not render the FromSecret env as a secretKeyRef")
	}

	// Local (compose overlay).
	compose := RenderCompose(RenderTarget{Plane: PlaneLocal}, services)
	if strings.Contains(compose, sentinelValue) {
		t.Error("compose overlay inlined a secret value")
	}
	if !strings.Contains(compose, "${EXAMPLE_SECRET}") {
		t.Error("compose overlay did not render the FromSecret env as a ${VAR} interpolation")
	}
}

// TestAgentGatewayJWTSecretIsVaultReference is the H8 regression: the agentgateway JWT signing key
// must be a stage-scoped Vault reference (EDEN_GATEWAY_JWT_SECRET_REF), never a raw env value nor a
// kubernetes-Secret secretKeyRef. The production Helm render emits the `{{ .Values.stage }}`
// placeholder; the local compose overlay pins the development stage. Driven through the REAL Catalog
// so a future catalog regression (a revert to FromSecret/raw) fails here.
func TestAgentGatewayJWTSecretIsVaultReference(t *testing.T) {
	t.Parallel()
	services := Catalog()

	helm := joinHelm(RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t"}, services))
	if !strings.Contains(helm, `vault://eden/{{ .Values.stage }}#agentgateway-jwt-signing-key`) {
		t.Errorf("helm did not render the stage-scoped JWT signing-key reference:\n%s", helm)
	}
	// The old raw env / kubernetes-Secret forms must be GONE from the production manifests.
	if strings.Contains(helm, "EDEN_GATEWAY_JWT_SECRET\n") || strings.Contains(helm, "name: EDEN_GATEWAY_JWT_SECRET\n") {
		t.Error("helm still renders the raw EDEN_GATEWAY_JWT_SECRET env (H8 regression)")
	}
	if strings.Contains(helm, "eden-gateway") || strings.Contains(helm, "jwt-secret") {
		t.Error("helm still renders the old eden-gateway/jwt-secret secretKeyRef (H8 regression)")
	}

	// Local: the development stage is correct here (the local plane IS development).
	compose := RenderCompose(RenderTarget{Plane: PlaneLocal}, services)
	if !strings.Contains(compose, `EDEN_GATEWAY_JWT_SECRET_REF: "vault://eden/development#agentgateway-jwt-signing-key"`) {
		t.Errorf("compose did not pin the development JWT signing-key reference:\n%s", compose)
	}
	if strings.Contains(compose, "${EDEN_GATEWAY_JWT_SECRET}") {
		t.Error("compose still renders the raw ${EDEN_GATEWAY_JWT_SECRET} interpolation (H8 regression)")
	}
}

// TestRenderComposeOmitsEmptyPortsBlock proves a probe-only (unpublished) service does not emit an
// empty `ports:` block (invalid compose).
func TestRenderComposeOmitsEmptyPortsBlock(t *testing.T) {
	t.Parallel()
	services := []ServiceSpec{{
		Name:  "agent-runtime",
		Image: "agent-runtime",
		Ports: []Port{{Name: "probe", Container: 8081, Host: 0}}, // unpublished
	}}
	out := RenderCompose(RenderTarget{Plane: PlaneLocal}, services)
	if strings.Contains(out, "ports:\n    environment:") {
		t.Error("an empty ports: block was emitted for a probe-only service")
	}
	// Sanity: the unpublished container port must not appear as a host mapping.
	if strings.Contains(out, "8081:8081") {
		t.Error("an unpublished probe port was host-mapped")
	}
}

// TestRenderStageScopedCredentialRef is the C1 regression: a FromVaultField credential reference must
// be STAGE-SCOPED, never the literal development path baked into the production chart. The production
// Helm render emits the `{{ .Values.stage }}` placeholder (values.yaml defaults stage: production) so
// a prod install resolves the production stage; the local compose overlay pins the development stage.
func TestRenderStageScopedCredentialRef(t *testing.T) {
	t.Parallel()
	services := []ServiceSpec{{
		Name:  "agent-runtime",
		Image: "agent-runtime",
		Env: []EnvVar{
			{Name: "EDEN_CREDENTIAL_REF", FromVaultField: "setup-token"},
		},
	}}

	helm := joinHelm(RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t"}, services))
	// The bug was the development path rendered into production. The placeholder must be present and
	// the literal development segment must be ABSENT from the production manifests.
	if !strings.Contains(helm, `vault://eden/{{ .Values.stage }}#setup-token`) {
		t.Errorf("helm did not render the stage-scoped credential reference:\n%s", helm)
	}
	if strings.Contains(helm, "vault://eden/development#") {
		t.Error("helm baked the DEVELOPMENT credential path into the production chart (C1 regression)")
	}
	if !strings.Contains(helm, "stage: production") {
		t.Error("values.yaml did not default the stage knob to production")
	}

	// A staging override re-points the default without re-spelling any reference.
	staging := joinHelm(RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t", Stage: "staging"}, services))
	if !strings.Contains(staging, "stage: staging") {
		t.Error("the Stage knob did not override the values.yaml default")
	}

	// Local: the development stage is correct here (the local plane IS development).
	compose := RenderCompose(RenderTarget{Plane: PlaneLocal}, services)
	if !strings.Contains(compose, `EDEN_CREDENTIAL_REF: "vault://eden/development#setup-token"`) {
		t.Errorf("compose did not pin the development credential reference:\n%s", compose)
	}
}

// TestCommittedManifestsMatchCatalog is the DRIFT GATE between the typed Catalog and the COMMITTED
// generated manifests (the render-verify analog of verify-openapi): it re-renders the Catalog with
// the exact defaults cmd/render uses and byte-compares against deploy/plane. A catalog/renderer
// change whose regen was forgotten — or a hand-edit of a generated file — fails HERE instead of
// shipping stale manifests. Fix a failure by regenerating (go run ./cmd/render), never by editing
// the committed yamls.
func TestCommittedManifestsMatchCatalog(t *testing.T) {
	t.Parallel()
	services := Catalog()

	// The cmd/render defaults (main.go flags): registry/tag/namespace/stage.
	helmTarget := RenderTarget{Plane: PlaneProduction, Registry: "ghcr.io/gophersys/eden", Tag: "latest", Namespace: "eden", Stage: "production"}
	for _, f := range RenderHelm(helmTarget, services) {
		committedPath := filepath.Join("..", "plane", "production", "chart", f.Path)
		committed, err := os.ReadFile(committedPath)
		if err != nil {
			t.Fatalf("read the committed chart file %s: %v (regenerate: go run ./cmd/render)", f.Path, err)
		}
		if string(committed) != f.Content {
			t.Errorf("committed %s DRIFTED from the catalog render — regenerate via `go run ./cmd/render` (never hand-edit)", f.Path)
		}
	}

	committedCompose, err := os.ReadFile(filepath.Join("..", "plane", "local", "platform.yaml"))
	if err != nil {
		t.Fatalf("read the committed compose overlay: %v", err)
	}
	if string(committedCompose) != RenderCompose(RenderTarget{Plane: PlaneLocal}, services) {
		t.Error("committed deploy/plane/local/platform.yaml DRIFTED from the catalog render — regenerate via `go run ./cmd/render`")
	}
}

// TestCatalogRostersFiveServices pins the deployable surface: the render catalog models exactly the
// five units the release channel builds + deploys (agent-runtime, agentgateway, orchestrator,
// platformgateway, frontend). A silent add/drop — a service that stops rendering, or a stray one that
// starts — fails here before it ships.
func TestCatalogRostersFiveServices(t *testing.T) {
	t.Parallel()
	want := map[string]bool{
		"agent-runtime": true, "agentgateway": true, "orchestrator": true,
		"platformgateway": true, "frontend": true,
	}
	got := map[string]bool{}
	for _, s := range Catalog() {
		got[s.Name] = true
	}
	if len(got) != len(want) {
		t.Fatalf("catalog rosters %d services %v, want %d %v", len(got), got, len(want), want)
	}
	for name := range want {
		if !got[name] {
			t.Errorf("catalog is missing service %q", name)
		}
	}
}

// TestTokenFileMountRenders proves the Vault token-file projection: every Vault-consuming service
// (agentgateway, orchestrator, agent-runtime, platformgateway) mounts the `eden-vault-token` Secret
// read-only at /vault/secrets/token (matching its EDEN_VAULT_TOKEN_FILE), and the frontend — which
// reaches no Vault — does NOT. The Secret is named, never a value (the no-leak contract).
func TestTokenFileMountRenders(t *testing.T) {
	t.Parallel()
	files := RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t"}, Catalog())
	byName := map[string]string{}
	for _, f := range files {
		byName[f.Path] = f.Content
	}

	for _, svc := range []string{"agentgateway", "orchestrator", "agent-runtime", "platformgateway"} {
		content := byName["templates/"+svc+"-deployment.yaml"]
		if content == "" {
			t.Fatalf("no deployment rendered for %q", svc)
		}
		// The mount references the Secret name + key + path, read-only. No value is ever inlined.
		for _, want := range []string{
			"volumeMounts:", "name: eden-vault-token", "mountPath: /vault/secrets",
			"subPath: token", "readOnly: true", "secretName: eden-vault-token", "key: token",
		} {
			if !strings.Contains(content, want) {
				t.Errorf("%s deployment missing token-file mount fragment %q", svc, want)
			}
		}
	}

	// The frontend is a static SPA with no Vault access — it must carry no token-file mount/volume.
	front := byName["templates/frontend-deployment.yaml"]
	if front == "" {
		t.Fatal("no deployment rendered for frontend")
	}
	if strings.Contains(front, "eden-vault-token") || strings.Contains(front, "volumeMounts:") {
		t.Error("frontend deployment must NOT mount the Vault token file (it reaches no Vault)")
	}
}

// TestPlatformGatewayVaultReferencesAreStageScoped proves the platformgateway catalog entry names the
// unified vault://eden/{{ .Values.stage }}#… mount (reconciled from the app spec's old
// vault://platformgateway/production#… path) for BOTH its secrets, and never inlines a value nor
// carries the old platformgateway mount.
func TestPlatformGatewayVaultReferencesAreStageScoped(t *testing.T) {
	t.Parallel()
	helm := joinHelm(RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t"}, Catalog()))
	for _, want := range []string{
		`vault://eden/{{ .Values.stage }}#platformgateway-jwt-signing-key`,
		`vault://eden/{{ .Values.stage }}#platformgateway-database-dsn`,
	} {
		if !strings.Contains(helm, want) {
			t.Errorf("platformgateway did not render the unified stage-scoped reference %q", want)
		}
	}
	// The OLD platformgateway mount path must be gone (reconciled to the eden mount).
	if strings.Contains(helm, "vault://platformgateway/") {
		t.Error("the old vault://platformgateway/… mount path is still rendered (reconcile to eden/)")
	}
}

// TestOrchestratorSpecShape proves the orchestrator entry: the agentgateway image with a command
// override selecting the second binary, the downward-API lease identity/namespace (fieldRef, never a
// literal), the Postgres password as a secretKeyRef with the DATABASE_URL interpolation, the bound
// ServiceAccount for leader election, and no inlined secret value.
func TestOrchestratorSpecShape(t *testing.T) {
	t.Parallel()
	files := RenderHelm(RenderTarget{Plane: PlaneProduction, Registry: "r", Tag: "t"}, Catalog())
	var orch string
	for _, f := range files {
		if f.Path == "templates/orchestrator-deployment.yaml" {
			orch = f.Content
		}
	}
	if orch == "" {
		t.Fatal("no orchestrator deployment rendered")
	}
	for _, want := range []string{
		`image: "{{ .Values.registry }}/agentgateway:{{ .Values.tag }}"`, // the SAME agentgateway image
		`command: ["/usr/local/bin/agentgateway-orchestrator"]`,          // the second binary
		"serviceAccountName: eden-orchestrator",                          // leader-election identity
		"fieldPath: metadata.name",                                       // per-replica lease identity
		"fieldPath: metadata.namespace",                                  // the lease namespace
		"secretKeyRef",                                                   // the Postgres password
		"name: eden-orchestrator-postgres",                               // the ONE plain k8s Secret
		"$(POSTGRES_PASSWORD)",                                           // the DATABASE_URL interpolation
		`value: "vault://eden/{{ .Values.stage }}#setup-token"`,          // the stage-scoped credential ref
	} {
		if !strings.Contains(orch, want) {
			t.Errorf("orchestrator deployment missing %q", want)
		}
	}
	// The Postgres password is a reference, never a value; no DSN password is ever inlined.
	if strings.Contains(orch, "password: ") && strings.Contains(orch, "password: eden") {
		t.Error("orchestrator inlined a Postgres password value")
	}
}

func joinHelm(files []HelmFile) string {
	var b strings.Builder
	for _, f := range files {
		b.WriteString(f.Content)
	}
	return b.String()
}
