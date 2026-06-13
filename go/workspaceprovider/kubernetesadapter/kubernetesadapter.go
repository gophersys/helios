// Package kubernetesadapter is the workspaceprovider Adapter for any conformant kubernetes
// distro — the ONLY place client-go is imported (05 §1). It realizes the one WorkspaceSpec
// vocabulary on kubernetes primitives: a workspace is a NAMESPACE (the ownership +
// tenancy unit, 07 §6) containing a single long-lived POD (a sleep-holding "infra"
// container the library drives Run/Exec/Files/Status over — the pod model). Mounts become
// emptyDir volumes (workdir/inputs/tmpfs); Resources become container requests+limits;
// the declared Egress becomes a NetworkPolicy (default-deny + declared-allow) WHERE the
// cluster's CNI enforces it — see Manifest for the honest CapEgressPolicy declaration. It
// translates kubernetes' native objects <-> the workspaceprovider vocabulary and owns
// rollback on partial failure (a failed Create deletes the namespace, so no orphan is
// left); the LIBRARY owns Handle assignment, idempotency, the state machine, status
// normalization, and secret-resolution timing.
//
// k3d (the default) and kind (the second conformance target) are the SAME adapter pointed
// at a different kubeconfig — there are NO k3d-isms or kind-isms in this package beyond the
// cluster lifecycle, which lives in the test harness, not here (ADR-0012: zero special
// code paths; central/BYO/local differ only in the injected client configuration).
package kubernetesadapter

import (
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

// Ownership-domain + tenancy label keys every namespace/pod this adapter authors carries,
// so List/Destroy scan exactly what Eden created (05 §5) and the test harness reaps zero
// orphans. The eden.* prefix mirrors the docker adapter's labels for cross-substrate
// symmetry.
const (
	ownerLabel        = "eden.workspaceprovider/owned"
	namespaceLabel    = "eden.workspaceprovider/namespace"
	nameLabel         = "eden.workspaceprovider/name"
	orgLabel          = "eden.workspaceprovider/org"
	projectLabel      = "eden.workspaceprovider/project"
	workdirAnnotation = "eden.workspaceprovider/workdir"
	// fingerprintAnnotation stores the library's spec fingerprint (a 64-char sha256 hex, over
	// the 63-char kubernetes label-value ceiling) so List can fold it back into the
	// Descriptor's Labels for the library's idempotency/conflict check.
	fingerprintAnnotation = "eden.workspaceprovider/spec-fingerprint"
)

// workspaceContainer is the name of the single long-lived container in a workspace pod —
// the holding process the library execs Run/Exec/Files into (the pod IS the workspace).
const workspaceContainer = "workspace"

// holdCommand keeps the workspace pod's container alive as a long-lived "infra" process the
// library drives Run/Exec/Files/Status over (the pod model). A primary workload
// (Connection.Run) and one-shot commands (Exec) are kubectl-execs INTO this container.
var holdCommand = []string{"sleep", "infinity"}

// Config is the kubernetes adapter's immutable construction input (the configuration
// pattern). It is parsed at the edge and frozen; New builds the client but dials NO
// apiserver. The central/local/BYO posture sets Kubeconfig at the composition root — the
// SAME adapter serves a central EKS cluster, a BYO cluster, and a local k3d/kind cluster,
// differing only in this value (ADR-0012).
type Config struct {
	// Kubeconfig is the path to the kubeconfig that selects the target cluster + context.
	// Empty means the in-cluster service-account config (the central control-plane posture)
	// falling back to the default loading rules (KUBECONFIG / ~/.kube/config).
	Kubeconfig string
	// Context overrides the kubeconfig's current-context (empty == the current-context).
	Context string
	// LabelNamespace scopes the ownership domain (the eden.namespace label value) and
	// prefixes the kubernetes namespaces this adapter creates; empty for single-tenant local.
	LabelNamespace string
}

// Adapter is the kubernetes workspaceprovider.Adapter. It holds a live typed client +
// the REST config (needed for the SPDY exec/attach plane) and the ownership-domain
// namespace. Safe for concurrent use (client-go's clientset is). Construct via New.
type Adapter struct {
	client     kubernetesClient
	restConfig *rest.Config
	namespace  string
	distro     string
	prePulled  map[string]bool
}

// Static assertion: *Adapter satisfies the workspaceprovider.Adapter port.
var _ workspaceprovider.Adapter = (*Adapter)(nil)

// New constructs the kubernetes Adapter. It LOADS and resolves the kubeconfig and builds
// the typed clientset (the one piece of edge wiring client-go requires) but performs NO
// apiserver I/O — the first apiserver call happens at Create/Dial/List/Destroy. It returns
// a wrapped SubstrateUnavailableError if the config cannot be loaded or the client cannot
// be constructed.
func New(configuration Config) (*Adapter, error) {
	restConfig := loadRESTConfig(configuration)
	clientset, err := kubernetes.NewForConfig(restConfig)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "kubernetesadapter.New: build clientset", err)
	}
	return newWithClient(clientWrapper{clientset: clientset, restConfig: restConfig}, restConfig, configuration), nil
}

// newWithClient is the shared constructor body used by New and the test seam: it wires the
// adapter over an already-built client + REST config, so a unit test can substitute a
// recording double without an apiserver.
func newWithClient(client kubernetesClient, restConfig *rest.Config, configuration Config) *Adapter {
	return &Adapter{
		client:     client,
		restConfig: restConfig,
		namespace:  configuration.LabelNamespace,
		distro:     "kubernetes",
		prePulled:  map[string]bool{},
	}
}

// loadRESTConfig resolves a *rest.Config from the Config: an explicit kubeconfig path (with
// an optional context override), else the in-cluster config, else the default loading rules
// (KUBECONFIG / ~/.kube/config) — so the same adapter serves central (in-cluster), BYO
// (explicit kubeconfig), and local k3d/kind (explicit kubeconfig) postures. It NEVER errors:
// New is the PURE constructor spine (no apiserver dial, no kubeconfig-must-exist), so a
// missing/unresolvable kubeconfig yields an empty config whose first APISERVER call fails —
// not New itself (mirroring the docker adapter, whose New does not require a running daemon).
func loadRESTConfig(configuration Config) *rest.Config {
	if configuration.Kubeconfig == "" {
		if inCluster, err := rest.InClusterConfig(); err == nil {
			return inCluster
		}
	}
	rules := clientcmd.NewDefaultClientConfigLoadingRules()
	if configuration.Kubeconfig != "" {
		rules.ExplicitPath = configuration.Kubeconfig
	}
	overrides := &clientcmd.ConfigOverrides{}
	if configuration.Context != "" {
		overrides.CurrentContext = configuration.Context
	}
	clientConfig := clientcmd.NewNonInteractiveDeferredLoadingClientConfig(rules, overrides)
	restConfig, err := clientConfig.ClientConfig()
	if err != nil {
		// Defer the failure to first use so New stays pure: an empty config builds a valid
		// clientset whose first apiserver call returns a (Skip-mappable) unavailable error.
		return &rest.Config{}
	}
	return restConfig
}

// Manifest declares the kubernetes substrate's capabilities (05 §3). kubernetes has full
// resource limits (requests+limits), PTY exec, log streaming, re-attach (a pod survives a
// control-plane restart), and namespace-per-project multi-tenancy. Bind mounts are
// distro-divergent (a local k3d/kind hostPath works; a managed cloud cluster forbids it),
// so CapBindMount is CapPartial. CapEgressPolicy is the HONEST escape hatch (05 §3): a
// NetworkPolicy is only ENFORCED where the CNI implements it — k3d/kind ship flannel, which
// does NOT enforce NetworkPolicy — so this adapter declares CapEgressPolicy ABSENT by
// default and the engine FLAGS rather than breaks (C18). CapPersistentVolume is CapPartial
// (a default StorageClass is distro-dependent); CapHibernate is CapAbsent (the deferred
// verb, Q4). Genuine k3d-vs-kind-vs-EKS divergence lives ONLY here.
func (a *Adapter) Manifest() workspaceprovider.CapabilityManifest {
	return workspaceprovider.CapabilityManifest{
		Distro: a.distro,
		Capabilities: map[workspaceprovider.Capability]workspaceprovider.CapStatus{
			workspaceprovider.CapExecPTY:          workspaceprovider.CapFull,
			workspaceprovider.CapResourceLimits:   workspaceprovider.CapFull,
			workspaceprovider.CapLogStream:        workspaceprovider.CapFull,
			workspaceprovider.CapReattach:         workspaceprovider.CapFull,
			workspaceprovider.CapMultiTenant:      workspaceprovider.CapFull,
			workspaceprovider.CapBindMount:        workspaceprovider.CapPartial,
			workspaceprovider.CapPersistentVolume: workspaceprovider.CapPartial,
			workspaceprovider.CapEgressPolicy:     workspaceprovider.CapAbsent,
			workspaceprovider.CapHibernate:        workspaceprovider.CapAbsent,
		},
	}
}

// WithDistro returns the adapter with its declared Distro identity set to the free-form
// telemetry string the harness knows (e.g. "k3d v5.9 / k3s", "kind v0.32"). It is
// telemetry/UI only (05 §3) and does NOT change any code path — distro transparency is the
// claim, this string is just the honest label. The test harness sets it so the manifest's
// Distro is truthful; production wiring leaves the default "kubernetes".
func (a *Adapter) WithDistro(distro string) *Adapter {
	if distro != "" {
		a.distro = distro
	}
	return a
}

// ownerLabels builds the label set every authored namespace/pod carries.
func (a *Adapter) ownerLabels(spec *workspaceprovider.WorkspaceSpec) map[string]string {
	labels := map[string]string{
		ownerLabel:     "true",
		namespaceLabel: labelValue(a.namespace),
		nameLabel:      labelValue(spec.Name),
	}
	if org := spec.Labels[workspaceprovider.LabelOrganization]; org != "" {
		labels[orgLabel] = labelValue(org)
	}
	if proj := spec.Labels[workspaceprovider.LabelProject]; proj != "" {
		labels[projectLabel] = labelValue(proj)
	}
	return labels
}

// k8sNamespace derives the kubernetes namespace name for a workspace within this adapter's
// ownership domain. It shares deriveNamespace with the Handle path so Create's namespace and
// Dial/Destroy's address are byte-identical.
func (a *Adapter) k8sNamespace(name string) string {
	return deriveNamespace(a.namespace, name)
}

// deriveNamespace is the single source of a workspace's deterministic kubernetes namespace
// from (ownershipNamespace, name). Both Create (via the adapter's own namespace) and Dial/
// Destroy (via the Handle's namespace) call it, so the native address round-trips exactly.
func deriveNamespace(ownershipNamespace, name string) string {
	base := "eden"
	if ownershipNamespace != "" {
		base += "-" + ownershipNamespace
	}
	return SanitizeName(base + "-" + name)
}

// SanitizeName makes s a valid RFC-1123 DNS label (kubernetes namespace/object name):
// lowercase, only [a-z0-9-], starting and ending alphanumeric, max 63 chars. Exported so
// the test harness derives a collision-proof name from a test name.
func SanitizeName(s string) string {
	var b strings.Builder
	prevDash := false
	for _, r := range strings.ToLower(s) {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9'):
			b.WriteRune(r)
			prevDash = false
		default:
			if !prevDash {
				b.WriteByte('-')
				prevDash = true
			}
		}
	}
	out := strings.Trim(b.String(), "-")
	if out == "" {
		out = "eden"
	}
	if len(out) > maxDNSLabel {
		out = strings.Trim(out[:maxDNSLabel], "-")
	}
	return out
}

// maxDNSLabel is the RFC-1123 DNS label length ceiling kubernetes enforces on
// namespace/object names.
const maxDNSLabel = 63

// labelValue makes s a valid kubernetes label VALUE (a stricter superset of names: max 63
// chars, [a-z0-9A-Z._-], starting+ending alphanumeric). An empty value is legal for a
// label. We reuse the DNS-label sanitizer (a safe subset) so a tenancy key like "org-7"
// survives unchanged while exotic input is normalized.
func labelValue(s string) string {
	if s == "" {
		return ""
	}
	return SanitizeName(s)
}

// IsClusterUnavailable reports whether err signals an unreachable apiserver (so the
// real-substrate harness can Skip rather than Fail on a machine without a cluster).
func IsClusterUnavailable(err error) bool {
	if err == nil {
		return false
	}
	if errors.KindOf(err) == errors.KindUnavailable {
		return true
	}
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "connection refused") ||
		strings.Contains(msg, "no such host") ||
		strings.Contains(msg, "could not find any host") ||
		strings.Contains(msg, "i/o timeout") ||
		strings.Contains(msg, "the server could not find the requested resource") ||
		strings.Contains(msg, "unable to load") ||
		strings.Contains(msg, "context deadline exceeded") ||
		strings.Contains(msg, "tls: ") ||
		strings.Contains(msg, "dial tcp")
}

// envVars renders NON-secret EnvVars onto kubernetes container env entries.
func envVars(env []workspaceprovider.EnvVar) []corev1.EnvVar {
	out := make([]corev1.EnvVar, 0, len(env))
	for _, e := range env {
		out = append(out, corev1.EnvVar{Name: e.Name, Value: e.Value})
	}
	return out
}
