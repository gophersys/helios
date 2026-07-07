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

func joinHelm(files []HelmFile) string {
	var b strings.Builder
	for _, f := range files {
		b.WriteString(f.Content)
	}
	return b.String()
}
