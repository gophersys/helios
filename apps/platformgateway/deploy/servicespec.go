// Package deploy is platformgateway's deploy surface: the ONE typed ServiceSpec the
// gateway deploys as, rendered to BOTH a docker-compose service (local) and a Helm chart template
// (production) by REUSING eden's deploy/servicespec renderer (ADR-0023: reuse, never reinvent — no
// hand-maintained compose/Helm drift). The image-tag-as-environment-contract holds: `<name>:local`
// for a compose load vs `<registry>/<name>:<tag>` for a registry push, one Dockerfile (deploy/).
//
// SKELETON: Spec() declares the gateway's typed shape (port, env NAMES + Secret references, probes).
// A generated app edits the field values; the RENDERING is owned entirely by the reused servicespec
// package, so this file never grows compose/Helm string-building.
package deploy

import (
	servicespec "github.com/gophersys/eden/deploy/servicespec"
)

// Spec returns platformgateway's typed ServiceSpec. It is the single source both renderers read:
// the env carries NAMES and Secret references only (never a value — the JWT key and DB DSN are
// Vault/K8s Secret references resolved at runtime), matching the composition root's EDEN_* contract.
func Spec() servicespec.ServiceSpec {
	return servicespec.ServiceSpec{
		Name:  "platformgateway",
		Image: "platformgateway",
		Ports: []servicespec.Port{
			{Name: "http", Container: 8080, Host: 8080},
		},
		Env: []servicespec.EnvVar{
			{Name: "EDEN_STAGE", Value: "production"},
			{Name: "EDEN_GATEWAY_ADDRESS", Value: ":8080"},
			{Name: "VAULT_ADDR", Value: "http://vault:8200"},
			{Name: "EDEN_VAULT_MODE", Value: "token-file"},
			{Name: "EDEN_VAULT_TOKEN_FILE", Value: "/vault/secrets/token"},
			// The JWT signing key + the Postgres DSN are Vault references resolved at runtime; the
			// manifest carries the REFERENCE, never the value (the secrets no-leak contract).
			{Name: "EDEN_GATEWAY_JWT_SECRET_REF", Value: "vault://platformgateway/production#jwt-signing-key"},
			{Name: "EDEN_GATEWAY_DATABASE_DSN_REF", Value: "vault://platformgateway/production#database-dsn"},
		},
		Replicas:       2, // stateless behind the JWT gate — scales horizontally
		Resources:      servicespec.ResourceEnvelope{CPUMillis: 500, MemoryMiB: 512, EphemeralMiB: 1024},
		Liveness:       &servicespec.Probe{Path: "/healthz/live", Port: 8080},
		Readiness:      &servicespec.Probe{Path: "/healthz/ready", Port: 8080},
		DependsOn:      []string{"vault", "postgres"},
		ServiceAccount: "platformgateway",
	}
}

// RenderCompose renders the local docker-compose service for the gateway (the dockeradapter world).
func RenderCompose(target servicespec.RenderTarget) string {
	return servicespec.RenderCompose(target, []servicespec.ServiceSpec{Spec()})
}

// RenderHelm renders the production Helm chart templates for the gateway (the kubernetesadapter
// world). Both renders read the SAME Spec() — one source of truth, both targets.
func RenderHelm(target servicespec.RenderTarget) []servicespec.HelmFile {
	return servicespec.RenderHelm(target, []servicespec.ServiceSpec{Spec()})
}
