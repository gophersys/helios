package servicespec

import (
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

// TestRenderNeverInlinesSecretValue is the secret-safety invariant: a render of a spec carrying a
// FromSecret env entry must NEVER inline a value — the production manifest references the Secret by
// name/key (valueFrom.secretKeyRef), and the local overlay uses a ${VAR} interpolation. Were a
// renderer to print the value, this catches it.
func TestRenderNeverInlinesSecretValue(t *testing.T) {
	t.Parallel()
	const sentinelValue = "SUPER-SECRET-VALUE-must-never-render"
	services := []ServiceSpec{{
		Name:  "agentgateway",
		Image: "agentgateway",
		Ports: []Port{{Name: "http", Container: 8080, Host: 8080}},
		Env: []EnvVar{
			{Name: "EDEN_GATEWAY_JWT_SECRET", FromSecret: &SecretKeyRef{SecretName: "eden-gateway", Key: "jwt-secret"}},
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
	if !strings.Contains(helm, "secretKeyRef") || !strings.Contains(helm, "jwt-secret") {
		t.Error("helm did not render the JWT secret as a secretKeyRef")
	}

	// Local (compose overlay).
	compose := RenderCompose(RenderTarget{Plane: PlaneLocal}, services)
	if strings.Contains(compose, sentinelValue) {
		t.Error("compose overlay inlined a secret value")
	}
	if !strings.Contains(compose, "${EDEN_GATEWAY_JWT_SECRET}") {
		t.Error("compose overlay did not render the JWT secret as a ${VAR} interpolation")
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

func joinHelm(files []HelmFile) string {
	var b strings.Builder
	for _, f := range files {
		b.WriteString(f.Content)
	}
	return b.String()
}
