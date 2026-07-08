package servicespec

// Catalog returns the Eden deployable services as typed ServiceSpecs — the one place the platform's
// deployable surface is declared. Both renderers (compose + Helm) consume exactly this. The
// supporting stack (NATS/Postgres/Vault) is deliberately ABSENT: it stands up out-of-band (ADR-0022
// #2), so the platform services below name it via env (EDEN_NATS_URL, etc.) but never reconcile it.
//
// The two services are the agent-pod runtime (the PID-1 workload that dogfoods the devcontainer
// base image) and the stateless gateway (the NATS→SSE bridge). Both run their container's MAIN
// process as the workload — the Entrypoint capability (ADR-0022 #4).
func Catalog() []ServiceSpec {
	return []ServiceSpec{
		agentRuntimeSpec(),
		agentGatewaySpec(),
		orchestratorSpec(),
		platformGatewaySpec(),
		frontendSpec(),
	}
}

// edenVaultTokenSecret is the ONE home for the production Vault token-file projection every
// Vault-consuming service declares (agentgateway, orchestrator, agent-runtime, platformgateway): the
// k8s Secret `eden-vault-token` (key `token`) mounted read-only at `/vault/secrets/token`, matching
// each service's EDEN_VAULT_TOKEN_FILE env. External Secrets / an operator materializes the Secret
// out-of-band; the render names it, never a value. The frontend (a static SPA, no Vault) omits it.
func edenVaultTokenSecret() *SecretMount {
	return &SecretMount{SecretName: "eden-vault-token", Key: "token", MountPath: "/vault/secrets/token"}
}

// edenVaultAddress is the in-cluster Vault Service DNS the production pods reach the app-Vault on
// (namespace `eden`). The FQDN form is the ratified deploy decision; within the `eden` namespace the
// short `vault` name resolves identically, so this is behavior-identical to a same-namespace short
// name while naming the service unambiguously.
const edenVaultAddress = "http://vault.eden.svc.cluster.local:8200"

// agentRuntimeSpec is the PID-1 agent-runtime pod (apps/agent-runtime): the harness sidecar that
// publishes the normalized event stream to JetStream and subscribes to the control subject. Its
// credential is resolved from Vault at boot (the production token-file sidecar path); its image
// dogfoods the .devcontainer base family.
func agentRuntimeSpec() ServiceSpec {
	return ServiceSpec{
		Name:     "agent-runtime",
		Image:    "agent-runtime",
		Replicas: 1, // one per agent in production (the orchestrator provisions N); the spec is the template
		Ports: []Port{
			{Name: "probe", Container: 8081, Host: 0}, // the kubelet probe; not host-published
		},
		Env: []EnvVar{
			{Name: "EDEN_NATS_URL", Value: "nats://nats:4222"},
			{Name: "EDEN_VAULT_MODE", Value: "token-file"}, // production: the K8s-SA sidecar token
			{Name: "EDEN_VAULT_TOKEN_FILE", Value: "/vault/secrets/token"},
			{Name: "VAULT_ADDR", Value: "http://vault:8200"},
			{Name: "EDEN_HARNESS", Value: "claude-code"},
			// Stage-scoped: production renders vault://eden/{{ .Values.stage }}#setup-token (stage
			// defaults to production), local pins the development stage — never the dev path in prod.
			{Name: "EDEN_CREDENTIAL_REF", FromVaultField: "setup-token"},
		},
		Resources:       ResourceEnvelope{CPUMillis: 1000, MemoryMiB: 2048, EphemeralMiB: 4096},
		Liveness:        &Probe{Path: "/live", Port: 8081},
		Readiness:       &Probe{Path: "/live", Port: 8081},
		DependsOn:       []string{"nats", "vault"},
		ServiceAccount:  "eden-agent",
		TokenFileSecret: edenVaultTokenSecret(),
	}
}

// agentGatewaySpec is the stateless NATS→SSE gateway (apps/agentgateway, cmd/agentgateway): any
// replica serves any session via JetStream durable replay, so it scales horizontally. Behind the
// dev-JWT auth even locally (ADR-0022 #3); like every OTHER Eden credential the JWT signing key is a
// stage-scoped Vault reference (EDEN_GATEWAY_JWT_SECRET_REF) the gateway resolves through the
// dual-mode Vault provider at boot, never an inlined value or a raw env secret. The Vault plane env
// mirrors agentRuntimeSpec's (the production token-file sidecar path).
func agentGatewaySpec() ServiceSpec {
	return ServiceSpec{
		Name:     "agentgateway",
		Image:    "agentgateway",
		Replicas: 2, // stateless → scale out; any replica serves any session
		Ports: []Port{
			{Name: "http", Container: 8080, Host: 8080},
		},
		Env: []EnvVar{
			{Name: "EDEN_GATEWAY_ADDRESS", Value: ":8080"},
			{Name: "EDEN_NATS_URL", Value: "nats://nats:4222"},
			{Name: "EDEN_VAULT_MODE", Value: "token-file"}, // production: the K8s-SA sidecar token
			{Name: "EDEN_VAULT_TOKEN_FILE", Value: "/vault/secrets/token"},
			{Name: "VAULT_ADDR", Value: "http://vault:8200"},
			// Stage-scoped: production renders vault://eden/{{ .Values.stage }}#agentgateway-jwt-signing-key
			// (stage defaults to production), local pins the development stage — never the dev path in prod.
			{Name: "EDEN_GATEWAY_JWT_SECRET_REF", FromVaultField: "agentgateway-jwt-signing-key"},
		},
		Resources:       ResourceEnvelope{CPUMillis: 500, MemoryMiB: 512, EphemeralMiB: 1024},
		Liveness:        &Probe{Path: "/healthz", Port: 8080},
		Readiness:       &Probe{Path: "/healthz", Port: 8080},
		DependsOn:       []string{"nats", "vault"},
		ServiceAccount:  "eden-agent",
		TokenFileSecret: edenVaultTokenSecret(),
	}
}

// orchestratorSpec is the per-project orchestrator role of the agentgateway app (W5): the SAME image
// as agentGatewaySpec with a `command` override selecting the second binary
// (/usr/local/bin/agentgateway-orchestrator, deploy/image/agentgateway.Dockerfile). It runs the
// reconcile loop under a real coordination.k8s.io/v1 Lease — replicas:3, but only the Lease holder
// reconciles (leader election needs a bound ServiceAccount so its projected token is the in-cluster
// kubeconfig). Env ported from apps/agentgateway/deploy/kubernetes/40-orchestrator-deployment.yaml,
// reconciled to the unified `eden` namespace DNS + the vault://eden/production#… mount. DATABASE_URL
// interpolates POSTGRES_PASSWORD from the k8s Secret eden-orchestrator-postgres (key `password`) —
// the ONE plain k8s Secret in the plane; every other credential is a Vault reference.
func orchestratorSpec() ServiceSpec {
	return ServiceSpec{
		Name:     "orchestrator",
		Image:    "agentgateway", // same image, different binary (command override below)
		Command:  []string{"/usr/local/bin/agentgateway-orchestrator"},
		Replicas: 3, // stateless HA: 3 serve verbs, 1 (the Lease holder) reconciles
		Ports: []Port{
			{Name: "http", Container: 8080, Host: 0}, // the read/admission API; not host-published
		},
		Env: []EnvVar{
			// Substrate: the namespace-per-workspace kubernetes adapter (in-cluster kubeconfig).
			{Name: "EDEN_WORKSPACE_SUBSTRATE", Value: "kubernetes"},
			// Leader election (lease.go): the contended Lease name; namespace + identity are the pod's
			// own (the downward API), rendered below.
			{Name: "EDEN_LEASE_NAME", Value: "eden-orchestrator"},
			{Name: "EDEN_LEASE_NAMESPACE", FromFieldRef: "metadata.namespace"},
			{Name: "EDEN_LEASE_IDENTITY", FromFieldRef: "metadata.name"}, // a distinct holder id per replica
			// Desired-state Postgres (the orchestrator's DesiredStore). The password is the ONE plain
			// k8s Secret; DATABASE_URL interpolates it via $(POSTGRES_PASSWORD) at container start.
			{Name: "POSTGRES_HOST", Value: "eden-postgres-0.eden-postgres.eden.svc.cluster.local"},
			{Name: "POSTGRES_USER", Value: "eden"},
			{Name: "POSTGRES_DB", Value: "eden"},
			{Name: "POSTGRES_PASSWORD", FromSecret: &SecretKeyRef{SecretName: "eden-orchestrator-postgres", Key: "password"}},
			// The password segment is the kubelet env-interpolation placeholder $(POSTGRES_PASSWORD),
			// resolved at container start from the secretKeyRef above — NOT a hardcoded credential (the
			// value never appears here; the manifest carries the reference only).
			{Name: "DATABASE_URL", Value: "postgres://eden:$(POSTGRES_PASSWORD)@eden-postgres-0.eden-postgres.eden.svc.cluster.local:5432/eden?sslmode=disable"}, //nolint:gosec // G101 false positive: $(…) is a kubelet interpolation placeholder, not an inlined password
			// Event bus.
			{Name: "EDEN_NATS_URL", Value: "nats://nats.eden.svc.cluster.local:4222"},
			// Per-project namespace prefix the kubernetesadapter scopes ownership by.
			{Name: "EDEN_LABEL_NAMESPACE", Value: "central"},
			// Secrets plane (dual-mode Vault, token-file mode): the supervisor's harness credential
			// rides every SpawnRequest as the opaque EDEN_CREDENTIAL_REF, resolved server-side.
			{Name: "EDEN_VAULT_MODE", Value: "token-file"},
			{Name: "EDEN_VAULT_TOKEN_FILE", Value: "/vault/secrets/token"},
			{Name: "VAULT_ADDR", Value: edenVaultAddress},
			{Name: "EDEN_HARNESS", Value: "claude-code"},
			// Stage-scoped: production renders vault://eden/{{ .Values.stage }}#setup-token.
			{Name: "EDEN_CREDENTIAL_REF", FromVaultField: "setup-token"},
		},
		Resources:       ResourceEnvelope{CPUMillis: 1000, MemoryMiB: 512, EphemeralMiB: 512},
		Liveness:        &Probe{Path: "/healthz", Port: 8080},
		Readiness:       &Probe{Path: "/healthz", Port: 8080},
		DependsOn:       []string{"nats", "vault", "postgres"},
		ServiceAccount:  "eden-orchestrator", // its projected token IS the in-cluster kubeconfig + the leaderelection identity
		TokenFileSecret: edenVaultTokenSecret(),
	}
}

// platformGatewaySpec is Eden's platform HTTP API (users + login + RBAC). It ports the typed spec
// from apps/platformgateway/deploy/servicespec.go (Spec()) into the render catalog — that spec was
// unwired (nothing rendered it), so it is materialized here. The two homes are kept in agreement:
// the app-side Spec() is updated coherently to name the SAME vault://eden/production#… references
// (the JWT signing key + the Postgres DSN), so this catalog entry is not a divergent copy. The mount
// path is NOT baked into the platformgateway Go code — it is parsed from the EDEN_GATEWAY_*_REF env
// at boot (secrets.ParseReference) — so reconciling platformgateway/production → eden/production is a
// pure env change requiring no code edit. Uses a Vault reference for BOTH secrets (not FromVaultField
// stage-scoping) because platformgateway's env carries the FULL vault:// URI (the app parses it),
// matching the local demo's EDEN_GATEWAY_JWT_SECRET_REF/…_DATABASE_DSN_REF shape.
func platformGatewaySpec() ServiceSpec {
	return ServiceSpec{
		Name:  "platformgateway",
		Image: "platformgateway",
		Ports: []Port{
			// Host 8081 locally (the demo's platformgateway port) so the compose overlay does not
			// collide with agentgateway's 8080; in production both listen on container 8080 behind
			// their own Service.
			{Name: "http", Container: 8080, Host: 8081},
		},
		Env: []EnvVar{
			{Name: "EDEN_STAGE", Value: "production"},
			{Name: "EDEN_GATEWAY_ADDRESS", Value: ":8080"},
			{Name: "EDEN_VAULT_MODE", Value: "token-file"},
			{Name: "EDEN_VAULT_TOKEN_FILE", Value: "/vault/secrets/token"},
			{Name: "VAULT_ADDR", Value: edenVaultAddress},
			// The JWT signing key + the Postgres DSN are Vault references resolved at runtime; the
			// manifest carries the REFERENCE, never the value (the secrets no-leak contract). Both
			// are stage-scoped so a staging install resolves the staging path via `--set stage=…`.
			{Name: "EDEN_GATEWAY_JWT_SECRET_REF", FromVaultField: "platformgateway-jwt-signing-key"},
			{Name: "EDEN_GATEWAY_DATABASE_DSN_REF", FromVaultField: "platformgateway-database-dsn"},
		},
		Replicas:        2, // stateless behind the JWT gate — scales horizontally
		Resources:       ResourceEnvelope{CPUMillis: 500, MemoryMiB: 512, EphemeralMiB: 1024},
		Liveness:        &Probe{Path: "/healthz/live", Port: 8080},
		Readiness:       &Probe{Path: "/healthz/ready", Port: 8080},
		DependsOn:       []string{"vault", "postgres"},
		ServiceAccount:  "platformgateway",
		TokenFileSecret: edenVaultTokenSecret(),
	}
}

// frontendSpec is the production SPA image (apps/frontend): the built static SvelteKit bundle served
// by nginx, which ALSO same-origin-proxies /gateway → agentgateway and /platform → platformgateway
// (apps/frontend/deploy/nginx.conf). It holds no secret and reaches no Vault — a pure static+proxy
// front door — so it declares no Env, no Vault plane, and no token-file mount. Port 8080 (nginx). It
// runs as its OWN dedicated ServiceAccount `eden-frontend` (not the namespace default) so the pod
// has a discrete identity to attach the ghcr image-pull secret to (the images are private) — every
// other service already binds a dedicated SA, so the frontend matches that posture.
func frontendSpec() ServiceSpec {
	return ServiceSpec{
		Name:     "frontend",
		Image:    "frontend",
		Replicas: 2, // stateless SPA server — scale out
		Ports: []Port{
			// Host 5173 locally (the demo's UI port) so the compose overlay does not collide with the
			// gateways' 8080; in production nginx listens on container 8080 behind the frontend Service.
			{Name: "http", Container: 8080, Host: 5173},
		},
		Resources:      ResourceEnvelope{CPUMillis: 250, MemoryMiB: 128, EphemeralMiB: 256},
		Liveness:       &Probe{Path: "/", Port: 8080},
		Readiness:      &Probe{Path: "/", Port: 8080},
		ServiceAccount: "eden-frontend",
	}
}
