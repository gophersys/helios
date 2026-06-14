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
	}
}

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
			{Name: "EDEN_CREDENTIAL_REF", Value: "vault://eden/development#setup-token"},
		},
		Resources:      ResourceEnvelope{CPUMillis: 1000, MemoryMiB: 2048, EphemeralMiB: 4096},
		Liveness:       &Probe{Path: "/live", Port: 8081},
		Readiness:      &Probe{Path: "/live", Port: 8081},
		DependsOn:      []string{"nats", "vault"},
		ServiceAccount: "eden-agent",
	}
}

// agentGatewaySpec is the stateless NATS→SSE gateway (apps/agentgateway, cmd/agentgateway): any
// replica serves any session via JetStream durable replay, so it scales horizontally. Behind the
// dev-JWT auth even locally (ADR-0022 #3); the JWT secret is a kubernetes Secret reference in
// production, never an inlined value.
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
			{Name: "EDEN_GATEWAY_JWT_SECRET", FromSecret: &SecretKeyRef{SecretName: "eden-gateway", Key: "jwt-secret"}},
		},
		Resources: ResourceEnvelope{CPUMillis: 500, MemoryMiB: 512, EphemeralMiB: 1024},
		Liveness:  &Probe{Path: "/healthz", Port: 8080},
		Readiness: &Probe{Path: "/healthz", Port: 8080},
		DependsOn: []string{"nats"},
	}
}
