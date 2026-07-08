// Package servicespec is the ONE typed source of truth for an Eden deployable service (ADR-0022
// #2): a single Go ServiceSpec renders to BOTH a docker-compose service (the `deploy/<plane>/local`
// world the workspaceprovider dockeradapter inhabits) AND a Helm chart template (the
// `deploy/<plane>/production` kubernetesadapter world) — no hand-maintained drift between the two.
//
// Image-tag-as-environment-contract: the SAME image name carries a `:local` tag a compose `up`
// loads vs a `<registry>/<name>:<tag>` a Helm `install` pulls; one Dockerfile per service. The
// supporting stack (NATS/JetStream + Postgres + Vault) is NOT modeled here — it stands up
// out-of-band (compose locally, the Helm chart's dependencies or a managed offering in production);
// the platform assumes it exists and does not reconcile it.
//
// This package is intentionally dependency-free (stdlib only, its own module, GOWORK=off): it is a
// build-time renderer, not a runtime library, so it never enters the agent dependency graph.
package servicespec

// Plane is the deployment axis a render targets: Local (docker-compose) or Production (Helm).
type Plane string

const (
	// PlaneLocal renders a docker-compose service: image `<name>:local`, host port mappings.
	PlaneLocal Plane = "local"
	// PlaneProduction renders a Helm Deployment+Service template: image `<registry>/<name>:<tag>`.
	PlaneProduction Plane = "production"
)

// Port is one exposed container port and its (local) host mapping.
type Port struct {
	// Name is the kubernetes Service port name (and the compose comment); HNS-1 full word.
	Name string
	// Container is the port the process listens on inside the container.
	Container int
	// Host is the loopback host port the compose mapping binds locally (0 == not published).
	Host int
}

// EnvVar is one environment entry rendered into both targets. A Secret value is NEVER inlined: it
// names a Vault reference (the agent resolves it through secrets/vaultadapter at runtime) or a
// kubernetes Secret key — the rendered manifests carry the NAME/REFERENCE only, never a value.
type EnvVar struct {
	// Name is the env var name (e.g. EDEN_NATS_URL, EDEN_CREDENTIAL_REF). Required.
	Name string
	// Value is a plain, non-secret literal (e.g. a NATS URL, a harness key). Empty if FromSecret
	// or FromVaultField.
	Value string
	// FromSecret, when set, names a kubernetes Secret + key the production manifest references via
	// valueFromSecretKeyRef (never an inlined value). Ignored for the local plane, which injects
	// the value from the loaded .env at runtime via compose's `environment:`/`env_file`.
	FromSecret *SecretKeyRef
	// FromVaultField, when set, names the FIELD segment (the part after '#') of a stage-scoped Vault
	// reference `vault://eden/<stage>#<field>`. The STAGE segment is environment-scoped, NOT a
	// literal: the production Helm render emits `vault://eden/{{ .Values.stage }}#<field>` (values.yaml
	// defaults `stage: production`) so a prod install never inherits the development path, while the
	// local compose render pins `vault://eden/development#<field>` (the local plane IS the development
	// stage). vaultStageRef is the one home for the reference shape — the renderers build it, the
	// catalog only names the field. Mutually exclusive with Value/FromSecret.
	FromVaultField string
	// FromFieldRef, when set, names a pod downward-API field path (e.g. "metadata.namespace",
	// "metadata.name") the production manifest references via valueFrom.fieldRef. The orchestrator's
	// leader-election identity (its pod name) and lease namespace arrive this way — a per-replica
	// value the render cannot know. Production-only: the local compose plane has no downward API, so a
	// FromFieldRef entry is OMITTED from the overlay (the orchestrator role runs only in production).
	// Mutually exclusive with Value/FromSecret/FromVaultField.
	FromFieldRef string
}

// SecretKeyRef names a kubernetes Secret and the key within it (the production secret seam).
type SecretKeyRef struct {
	SecretName string
	Key        string
}

// SecretMount projects a kubernetes Secret onto a file inside the container (production only). It is
// the typed seam for the Vault token-file the production pods read: External Secrets / an operator
// materializes the named Secret out-of-band, and the render mounts it read-only at MountPath so the
// dual-mode Vault provider's token-file mode (EDEN_VAULT_TOKEN_FILE) resolves it. The rendered
// manifest names the Secret + key + path only — never a value. The local compose plane ignores it
// (locally the Vault provider authenticates via userpass, not a mounted token file), so a
// SecretMount is a production-only concern that never touches the committed overlay.
type SecretMount struct {
	// SecretName is the kubernetes Secret the token file is projected from (e.g. "eden-vault-token").
	SecretName string
	// Key is the field within the Secret projected as the file (e.g. "token").
	Key string
	// MountPath is the absolute file path the projected key is mounted at (e.g.
	// "/vault/secrets/token"). It matches the EDEN_VAULT_TOKEN_FILE env the service reads.
	MountPath string
}

// volumeName is the deterministic volume name a SecretMount renders under (the Secret name is a
// valid DNS-1123 label, so it doubles as the volume name — one Secret, one volume). Keeping the
// derivation here (not spelled at the call site) means the Deployment volume and volumeMount always
// agree on the name.
func (m SecretMount) volumeName() string { return m.SecretName }

// mountDir is the directory the projected key is mounted into (a Secret volume mounts a directory;
// the projected file lands at mountDir/<subPath-basename>). It is MountPath's parent.
func (m SecretMount) mountDir() string {
	i := len(m.MountPath) - 1
	for i >= 0 && m.MountPath[i] != '/' {
		i--
	}
	if i <= 0 {
		return "/"
	}
	return m.MountPath[:i]
}

// mountFile is the basename of MountPath — the projected key's filename (the Secret volume's item
// path). Splitting file from dir lets the render project ONLY this key into the dir (subPath) so an
// unrelated file in the same dir is not clobbered.
func (m SecretMount) mountFile() string {
	i := len(m.MountPath) - 1
	for i >= 0 && m.MountPath[i] != '/' {
		i--
	}
	return m.MountPath[i+1:]
}

// ResourceEnvelope is the CPU/memory request+limit (production only; compose ignores it locally).
type ResourceEnvelope struct {
	CPUMillis    int // e.g. 1000 == 1 vCPU
	MemoryMiB    int
	EphemeralMiB int
}

// Probe is an HTTP liveness/readiness probe path + port (the kubelet probe; compose healthcheck).
type Probe struct {
	Path string
	Port int
}

// ServiceSpec is the typed, fully-resolved description of ONE deployable Eden service. It is the
// single source both renderers read — change a field once, both the compose service and the Helm
// template move together.
type ServiceSpec struct {
	// Name is the service slug (HNS-1 full words, e.g. "agentgateway", "agent-runtime"). It is the
	// compose service name, the kubernetes Deployment/Service name, and the image name stem.
	Name string
	// Image is the image name stem (without tag). Local renders `<Image>:local`; production renders
	// `<Registry>/<Image>:<Tag>`. One Dockerfile per service builds it.
	Image string
	// Command overrides the image entrypoint (the container's main process IS the workload — the
	// workspaceprovider Entrypoint capability, ADR-0022 #4). Empty == the image default.
	Command []string
	// Ports are the exposed ports (the gateway's HTTP, the agent-runtime's probe).
	Ports []Port
	// Env are the environment entries (non-secret literals + Vault/Secret references).
	Env []EnvVar
	// Replicas is the production Deployment replica count (compose runs 1 locally).
	Replicas int
	// Resources is the production resource envelope (ignored locally).
	Resources ResourceEnvelope
	// Liveness / Readiness are the HTTP probes (the kubelet probe / compose healthcheck).
	Liveness  *Probe
	Readiness *Probe
	// DependsOn names the supporting-stack services this one waits on locally (compose depends_on).
	// Production assumes the stack exists out-of-band, so this is local-only ordering.
	DependsOn []string
	// ServiceAccount is the kubernetes ServiceAccount the pod runs as (production; the Vault
	// sidecar's token-file auth path binds to it — ADR-0022 #1). Empty == "default".
	ServiceAccount string
	// TokenFileSecret, when set, projects a kubernetes Secret onto a file the production pod reads —
	// the Vault token-file (EDEN_VAULT_TOKEN_FILE) the dual-mode Vault provider resolves in token-file
	// mode. Every Vault-consuming service (agentgateway, orchestrator, agent-runtime, platformgateway)
	// declares it; the frontend (a static SPA with no Vault access) does not. Production-only: the
	// local compose overlay ignores it (local Vault auth is userpass, not a mounted token). Nil == no
	// projected token file.
	TokenFileSecret *SecretMount
}

// RenderTarget bundles the cross-cutting knobs a render needs that are NOT per-service: the image
// registry + tag (production) and the namespace.
type RenderTarget struct {
	Plane     Plane
	Registry  string // e.g. "ghcr.io/gophersys/eden" (production image prefix)
	Tag       string // e.g. "1.0.0" or a git sha (production image tag)
	Namespace string // kubernetes namespace (production)
	// Stage is the deployment STAGE (development/test/staging/production) the production values.yaml
	// defaults its `stage:` knob to — the segment a FromVaultField env entry resolves under. Empty
	// defaults to "production" (a prod install must never inherit the development credential path).
	// The local plane is always the development stage and ignores this.
	Stage string
}

// vaultHelmStagePlaceholder is the Helm value reference the production render substitutes for the
// stage segment of a FromVaultField reference. The operator sets it via values.yaml `stage:` (the
// render defaults it to "production"), so re-pointing every credential path to a different stage is
// one `--set stage=<stage>`.
const vaultHelmStagePlaceholder = "{{ .Values.stage }}"

// vaultStageRef is the ONE home for the stage-scoped Vault reference shape
// `vault://eden/<stage>#<field>` (10 §9: one concept, one home). Both renderers build a
// FromVaultField entry through it — production passes the Helm `{{ .Values.stage }}` placeholder,
// local passes the literal "development" stage — so the reference grammar is never re-spelled.
func vaultStageRef(stage, field string) string {
	return "vault://eden/" + stage + "#" + field
}

// ImageReference returns the fully-qualified image reference for the target plane (the
// image-tag-as-environment-contract: `<name>:local` load vs `<registry>/<name>:<tag>` push).
func (s ServiceSpec) ImageReference(target RenderTarget) string {
	if target.Plane == PlaneLocal {
		return s.Image + ":local"
	}
	registry := target.Registry
	tag := target.Tag
	if tag == "" {
		tag = "latest"
	}
	if registry == "" {
		return s.Image + ":" + tag
	}
	return registry + "/" + s.Image + ":" + tag
}
