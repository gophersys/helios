// Package runtime is the gateway's runtime-environment seam: it detects which deployment SUBSTRATE
// the process runs on (docker vs kubernetes), reusing the orchestrator's F1 Substrate enum as the
// canonical declaration rather than minting a parallel concept (one concept, one home — 10 §9). The
// composition root reads the detected substrate so the server records where it runs and a future
// deploy path can branch on it.
package runtime

import (
	"os"

	"github.com/gophersys/libs/go/orchestrator"
)

// Substrate is the gateway's view of the deployment substrate. It carries the orchestrator's F1
// Substrate enum (the canonical "kubernetes | docker" declaration, ADR-0012) plus a String() the
// composition root logs — the orchestrator type intentionally has no String, so the rendering lives
// here, at the consumer, not as a redefinition of the enum.
type Substrate struct {
	// Kind is the reused orchestrator F1 enum value (SubstrateKubernetes | SubstrateDocker).
	Kind orchestrator.Substrate
	// bareProcess records the finer non-kubernetes distinction the F1 enum does not carry: true when
	// the process runs directly on a host (no /.dockerenv marker), false inside a docker container. It
	// is unexported so the canonical concept stays the orchestrator enum; String/IsBareProcess expose it.
	bareProcess bool
}

// String renders the detected substrate for logs/telemetry (the full HNS-1 words, never "k8s"). The
// non-kubernetes case distinguishes a bare host process from a docker container for the operator,
// without that distinction widening the canonical F1 enum.
func (s Substrate) String() string {
	if s.Kind == orchestrator.SubstrateKubernetes {
		return "kubernetes"
	}
	if s.bareProcess {
		return "bare-process"
	}
	return "docker"
}

// IsKubernetes reports whether the gateway runs on the kubernetes substrate (the default).
func (s Substrate) IsKubernetes() bool { return s.Kind == orchestrator.SubstrateKubernetes }

// IsBareProcess reports whether the gateway runs as a plain host process (not kubernetes, not a
// docker container) — the local-development/no-orchestrator case. It is the finer signal a deploy
// branch or a startup log reads; the Kind stays the canonical non-kubernetes adapter value.
func (s Substrate) IsBareProcess() bool { return s.bareProcess }

// DetectSubstrate resolves the deployment substrate, mirroring the orchestrator's F1 adapter
// selection, with the precedence the prompt fixes:
//
//  1. EDEN_SUBSTRATE override — an explicit hint ("docker" | "kubernetes") wins outright (the
//     configuration override the composition root passes through). An unrecognized hint is ignored
//     and detection continues, so a typo never silently pins the wrong substrate.
//  2. kubernetes — the in-cluster signal: KUBERNETES_SERVICE_HOST in the environment OR the kubelet's
//     projected ServiceAccount token file. Either marks a real pod.
//  3. docker — the /.dockerenv marker the docker runtime drops into every container's root.
//  4. bare process — no kubernetes signal and no container marker: a plain local/host process.
//
// The orchestrator F1 enum is the canonical, frozen "kubernetes | docker" declaration (ADR-0012,
// one concept one home — 10 §9); it has no third "bare process" value and this app does not mint a
// parallel one. So both the container (3) and the bare-process (4) cases resolve to the SAME
// non-kubernetes adapter value (SubstrateDocker — "the local/host world"); IsBareProcess exposes the
// finer (4)-vs-(3) distinction for a log line or a future deploy branch without widening the enum.
func DetectSubstrate(hint string) Substrate {
	switch hint {
	case "docker":
		return Substrate{Kind: orchestrator.SubstrateDocker}
	case "kubernetes":
		return Substrate{Kind: orchestrator.SubstrateKubernetes}
	}
	if inKubernetes() {
		return Substrate{Kind: orchestrator.SubstrateKubernetes}
	}
	// Non-kubernetes: both a docker container and a bare host process map to the non-kubernetes
	// adapter value; the bare/container distinction rides bareProcess, not a new enum value.
	return Substrate{Kind: orchestrator.SubstrateDocker, bareProcess: !inContainer()}
}

// serviceAccountTokenPath is the in-cluster ServiceAccount token the kubelet projects into every
// pod; its PRESENCE (not its contents — this is a path, never a credential value) is the canonical
// "I am running inside kubernetes" signal.
//
//nolint:gosec // G101: this is the well-known projected-token PATH, not a hardcoded credential.
const serviceAccountTokenPath = "/var/run/secrets/kubernetes.io/serviceaccount/token" //nolint:gosec // path, not a secret

// dockerEnvMarker is the empty file the docker runtime drops into a container's root filesystem; its
// PRESENCE is the canonical "I am running inside a docker container" signal (a path, not a secret).
const dockerEnvMarker = "/.dockerenv"

// inKubernetes reports whether the process runs inside a kubernetes pod: the KUBERNETES_SERVICE_HOST
// env the kubelet injects, or the projected SA token file. It reads env + filesystem ONCE at the
// composition edge; the libraries stay pure.
func inKubernetes() bool {
	if os.Getenv("KUBERNETES_SERVICE_HOST") != "" {
		return true
	}
	if _, err := os.Stat(serviceAccountTokenPath); err == nil {
		return true
	}
	return false
}

// inContainer reports whether the process runs inside a docker container (the /.dockerenv marker is
// present). Its absence, given we are already not in kubernetes, means a bare host process.
func inContainer() bool {
	_, err := os.Stat(dockerEnvMarker)
	return err == nil
}
