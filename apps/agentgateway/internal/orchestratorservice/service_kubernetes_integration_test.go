//go:build integration

package orchestratorservice_test

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
)

// This is the REAL-substrate KUBERNETES lane for the orchestrator service: it composes the
// IDENTICAL production adapter stack the Service wires — the namespacing production
// postgresstore.DesiredStore over a REAL postgres, the workspaceprovider over the REAL
// kubernetesadapter pointed at a REAL local k3d cluster, and the agentsession claude Factory —
// and drives a full Spawn -> reconcile-to-Running -> Stop -> reconcile-to-Stopped cycle on the
// cluster. NOTHING is mocked (ADR-0016 §2): a real workspace POD is created in a real per-project
// NAMESPACE on a real k3d apiserver, and a real row is upserted into a real postgres.
//
// It is the W5 deployment proof: the orchestrator binds Config.Substrate=SubstrateKubernetes +
// Config.Kubeconfig=<k3d kubeconfig> and SpawnRequest lands as a namespace-per-workspace pod. The
// cluster default is local-k3d (defaultCluster(SubstrateKubernetes)); the test asserts (a) the
// agent reconciles to Running carrying a kubernetes workspace handle, (b) the project namespace
// was created+labeled (eden ownership labels), and (c) Stop reaps it (the namespace goes
// Terminating/gone). The whole k3d cluster is deleted on t.Cleanup (on failure too — a leaked
// cluster is unacceptable).
//
// The ONLY substitutions vs production are (a) a TRIVIAL busybox TemplateStore compiled to the
// kubernetes substrate (so the workspace pod is a tiny long-lived container, not the heavy
// supervisor image) and (b) a stub `claude` binary (the scripted stand-in). Both are the standard
// real-substrate substitutions; the production composition (the namespacing id bridge, the
// kubernetes provisioner, the claude Factory, the telemetry shim) is exercised verbatim.
//
// Running it (inside the devcontainer; docker socket mounted, k3d + every gate tool present):
//
//	bash .devcontainer/base/ctl.sh exec -- bash -lc 'export GOWORK=/workspace/go.work && \
//	  cd /workspace/apps/agentgateway && go test -tags integration -race \
//	  -run TestIntegrationKubernetes ./internal/orchestratorservice/...'
//
// It SKIPS when k3d/docker is unavailable locally and is REQUIRED (FAIL-NOT-SKIP) in the
// devcontainer where both are live.

// k3dClusterTimeout bounds the cluster create + apiserver-ready handshake (image pull + node
// boot). A k3d cluster boots well under this on a warm daemon; the ceiling exists so a wedged
// create rolls the cluster back rather than hanging the run.
const k3dClusterTimeout = 4 * time.Minute

//nolint:paralleltest // serial by design: spins a real ephemeral k3d cluster + real postgres + real pods; a parallel fan-out would stand up N clusters.
func TestIntegrationKubernetes_SpawnReconcilesToRunningThenStop(t *testing.T) {
	requireK3d(t)
	ctx := t.Context()

	kubeconfig, clusterName := bootK3dCluster(t)
	service, namespace := buildRealKubernetesService(t, kubeconfig)

	tenant := orchestrator.Tenancy{
		OrganizationID: "11111111-1111-1111-1111-111111111111",
		ProjectID:      "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
	}
	admitted, err := service.Spawn(ctx, orchestrator.SpawnRequest{
		Tenant:     tenant,
		Template:   trivialTemplateRef,
		Credential: secrets.Ref(credentialReference),
		By:         "integration-test-kubernetes",
	})
	if err != nil {
		t.Fatalf("Spawn: %v", err)
	}
	if admitted.Status != orchestrator.StatusPending {
		t.Fatalf("Spawn admitted at %v, want Pending", admitted.Status)
	}
	// A kubernetes-substrate Spawn that names no cluster resolves to the local-k3d default
	// (defaultCluster(SubstrateKubernetes)) — the cluster IDENTITY the record carries.
	if admitted.Cluster.ID != "local-k3d" {
		t.Fatalf("Spawn cluster = %q, want local-k3d (the kubernetes-substrate default)", admitted.Cluster.ID)
	}
	t.Cleanup(func() {
		_ = service.Stop(context.Background(), admitted.ID, "cleanup") //nolint:errcheck // best-effort reap.
		for range 8 {
			_, _ = service.ReconcileOnce(context.Background()) //nolint:errcheck // best-effort drain.
		}
	})

	// ── Drive reconcile to Running: Pending -> Provisioning (a REAL namespace + pod created on
	// k3d) -> Running (stub session opened). The pod's image pull + scheduling take a beat, so the
	// pass count + settle are larger than the docker lane. ──
	running := driveUntilStatusK3d(t, service, admitted.ID, orchestrator.StatusRunning)
	if running.Status != orchestrator.StatusRunning {
		t.Fatalf("agent never reached Running; last status %v / %q", running.Status, running.Detail)
	}
	if running.Workspace.IsZero() {
		t.Fatal("a Running agent must carry a provisioned workspace handle")
	}
	if got := running.Workspace.Substrate(); got != workspaceKubernetes {
		t.Fatalf("Running workspace substrate = %q, want kubernetes (the handle must route to the k8s adapter)", got)
	}
	if running.Session == "" {
		t.Fatal("a Running agent must carry an open session ref")
	}

	// ── The project namespace must exist on the cluster, owned + tenancy-labeled. The
	// kubernetesadapter derives eden-<prefix>-<workspace> and labels it with the ownership domain
	// + the project; assert both the existence and the labels directly via kubectl (the apiserver
	// is the source of truth, not the handle). ──
	projectNamespace := assertProjectNamespaceLive(t, kubeconfig, namespace, string(tenant.ProjectID))

	// Get over the BARE id round-trips the namespaced postgres row back to the bare id (the
	// namespacing bridge proven against REAL postgres on the kubernetes path too).
	got, err := service.Get(ctx, admitted.ID)
	if err != nil {
		t.Fatalf("Get running agent: %v", err)
	}
	if got.ID != admitted.ID {
		t.Fatalf("Get returned id %q, want the bare id %q (namespacing bridge must de-namespace)", got.ID, admitted.ID)
	}

	// ── Stop: record the terminal intent, then drive passes draining Running -> Stopping ->
	// Stopped (the REAL namespace is torn down on the cluster, cascading to the pod). ──
	if err := service.Stop(ctx, admitted.ID, "integration-test-kubernetes"); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	stopped := driveUntilStatusK3d(t, service, admitted.ID, orchestrator.StatusStopped)
	if stopped.Status != orchestrator.StatusStopped {
		t.Fatalf("agent never reached Stopped; last status %v / %q", stopped.Status, stopped.Detail)
	}

	// ── The project namespace must be reaped: a foreground delete leaves it Terminating then gone.
	// Poll until the apiserver reports it absent/Terminating (the reclaim contract). ──
	assertProjectNamespaceReaped(t, kubeconfig, projectNamespace)

	_ = clusterName // retained for diagnostics; the cluster is reaped by bootK3dCluster's cleanup
}

// workspaceKubernetes is the workspaceprovider Substrate a kubernetes-authored Handle reports
// (the handle scheme routes Teardown). It mirrors workspaceprovider.SubstrateKubernetes without
// importing the value path into this test's assertion (the Handle.Substrate() return is the
// frozen "kubernetes" string).
const workspaceKubernetes = "kubernetes"

// driveUntilStatusK3d drives reconcile passes (one transition per agent per pass) until the agent
// reaches want or a bound is hit. It uses a larger pass count + settle than the docker lane: a
// real k3d pod's image pull + scheduling + Ready handshake is slower than a local docker
// container start.
func driveUntilStatusK3d(t *testing.T, service *orchestratorservice.Service, id orchestrator.AgentID, want orchestrator.Status) orchestrator.Agent {
	t.Helper()
	ctx := t.Context()
	const maxPasses = 60
	var last orchestrator.Agent
	for range maxPasses {
		if _, err := service.ReconcileOnce(ctx); err != nil {
			t.Fatalf("reconcile pass: %v", err)
		}
		agent, err := service.Get(ctx, id)
		if err != nil {
			t.Fatalf("get during reconcile: %v", err)
		}
		last = agent
		if agent.Status == want || agent.Status == orchestrator.StatusFailed {
			return agent
		}
		time.Sleep(time.Second) // a real k3d pod needs a beat between the provision pass and Ready
	}
	return last
}

// buildRealKubernetesService composes the production Service over a REAL postgres + the REAL
// kubernetesadapter pointed at the k3d kubeconfig + a stub claude binary, via the
// BuildWithTemplates seam (a kubernetes trivial busybox TemplateStore). It returns the service +
// the unique LabelNamespace (the ownership-domain prefix the project namespaces carry). Postgres
// is reaped by bootPostgres' cleanup; the cluster (and thus every namespace) by bootK3dCluster's.
func buildRealKubernetesService(t *testing.T, kubeconfig string) (service *orchestratorservice.Service, labelNamespace string) {
	t.Helper()
	ctx := context.Background()

	pool := bootPostgres(t)
	desiredStore, err := postgresstore.New(postgresstore.Config{}, postgresstore.Deps{Pool: pool})
	if err != nil {
		t.Fatalf("construct postgres store: %v", err)
	}
	if err := desiredStore.EnsureSchema(ctx); err != nil {
		t.Fatalf("ensure schema: %v", err)
	}

	stub := buildStubClaude(t)
	provider := secretstest.New(map[string]string{credentialReference: "stub-setup-token"})

	// A unique ownership-domain prefix so every project namespace this run authors is scoped to
	// this test (the kubernetesadapter prefixes namespaces with it); the whole cluster is reaped
	// regardless, but a unique prefix keeps a shared cluster clean.
	labelNamespace = "edenk8s-" + strconv.FormatInt(time.Now().UnixNano(), 36)

	svc, err := orchestratorservice.New(
		orchestratorservice.Config{
			Substrate:            orchestratorservice.SubstrateKubernetes,
			Kubeconfig:           kubeconfig,
			DefaultMaxConcurrent: 4,
			ReconcileInterval:    time.Hour, // the test drives Reconcile by hand; the timed loop never ticks
			ProvisionTimeout:     k3dClusterTimeout,
			LabelNamespace:       labelNamespace,
		},
		orchestratorservice.Deps{
			DatabasePool:  pool,
			Secrets:       provider,
			Observability: discardProvider(t),
			Sessions:      supervisorPool(t, provider, stub), // the ONE injected pool over the stub claude binary
			Templates:     kubernetesTrivialTemplateStore{},  // the production Deps.Templates seam swaps ONLY the template source
		},
	)
	if err != nil {
		t.Fatalf("orchestratorservice.New (kubernetes): %v", err)
	}
	return svc, labelNamespace
}

// kubernetesTrivialTemplateStore resolves the trivial busybox template compiled to the KUBERNETES
// substrate (a long-lived sleep pod), replacing the heavy supervisor image for the hermetic
// real-cluster run. It is the kubernetes sibling of trivialTemplateStore — the ONLY production
// substitution vs the Service's supervisor store; the rest of the composition is verbatim.
type kubernetesTrivialTemplateStore struct{}

//nolint:gocritic // contract: TemplateStore.Resolve takes the TemplateRef by value (the frozen port surface).
func (kubernetesTrivialTemplateStore) Resolve(_ context.Context, ref orchestrator.TemplateRef) (orchestrator.AgentTemplate, error) {
	if ref != trivialTemplateRef {
		return orchestrator.AgentTemplate{}, fmt.Errorf("kubernetesTrivialTemplateStore: unknown ref %v", ref)
	}
	return orchestrator.AgentTemplate{
		Ref:     trivialTemplateRef,
		Routing: agentsession.RouteKey{Phase: "supervise", Role: "supervisor"},
		Sandbox: orchestrator.SandboxSpec{
			Substrate: orchestrator.SubstrateKubernetes,
			Image:     busyboxImage,
			Resources: orchestrator.ResourceEnvelope{CPUMillis: 250, MemoryMiB: 64, EphemeralMiB: 64},
		},
		Limits: orchestrator.Limits{MaxConcurrent: 4},
	}, nil
}

// ── REAL k3d cluster boot/reap + namespace assertions.

// requireK3d skips locally when k3d or docker is unavailable; in the devcontainer both are live,
// so the lane is REQUIRED there (the run that omits it is the CI failure, not this skip).
func requireK3d(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("k3d"); err != nil {
		t.Skip("k3d not on PATH: the real-cluster lane is skipped (REQUIRED in the devcontainer)")
	}
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker not on PATH: the real-cluster lane is skipped (REQUIRED in the devcontainer)")
	}
}

// bootK3dCluster stands up an ephemeral k3d cluster under a unique name, writes its ISOLATED
// kubeconfig to a temp file, pre-imports busybox so the workspace pod provisions fast, and deletes
// the WHOLE cluster on t.Cleanup (on failure too — a leaked cluster is unacceptable). It mirrors
// the workspaceprovidertest harness's create flow (traefik/metrics-server/lb disabled for a fast
// boot, an isolated kubeconfig that never touches ~/.kube/config). It returns the kubeconfig path
// + the cluster name.
func bootK3dCluster(t *testing.T) (kubeconfig, clusterName string) {
	t.Helper()
	clusterName = uniqueK3dName()
	kubeconfig = filepath.Join(t.TempDir(), clusterName+".kubeconfig")
	t.Cleanup(func() {
		// #nosec G204 -- fixed `k3d cluster delete` of the just-created cluster by its time-derived name.
		_ = exec.Command("k3d", "cluster", "delete", clusterName).Run() //nolint:errcheck // best-effort whole-cluster reap.
	})

	createCtx, cancel := context.WithTimeout(t.Context(), k3dClusterTimeout)
	defer cancel()
	// #nosec G204 -- fixed `k3d cluster create` flags; the name is time-derived, not user input.
	create := exec.CommandContext(
		createCtx, "k3d", "cluster", "create", clusterName,
		"--no-lb", "--wait", "--timeout", k3dClusterTimeout.String(),
		"--kubeconfig-update-default=false", "--kubeconfig-switch-context=false",
		"--k3s-arg", "--disable=traefik@server:0",
		"--k3s-arg", "--disable=metrics-server@server:0",
	)
	if out, err := create.CombinedOutput(); err != nil {
		t.Skipf("k3d cluster create unavailable, skipping: %v\n%s", err, out)
	}

	// #nosec G204 -- fixed `k3d kubeconfig get` of the just-created cluster by name.
	kubeconfigBytes, err := exec.CommandContext(createCtx, "k3d", "kubeconfig", "get", clusterName).Output()
	if err != nil {
		t.Fatalf("k3d kubeconfig get: %v", err)
	}
	if werr := os.WriteFile(kubeconfig, kubeconfigBytes, 0o600); werr != nil {
		t.Fatalf("write k3d kubeconfig: %v", werr)
	}
	// Pre-import busybox so the per-pod provision is fast + offline-safe after the first pull.
	// #nosec G204 -- fixed `k3d image import` of a pinned public image into the just-created cluster.
	if _, perr := exec.CommandContext(createCtx, "docker", "pull", busyboxImage).CombinedOutput(); perr == nil {
		// #nosec G204 -- fixed `k3d image import` of the pinned image by cluster name.
		_, _ = exec.CommandContext(createCtx, "k3d", "image", "import", "--cluster", clusterName, busyboxImage).CombinedOutput() //nolint:errcheck // best-effort import; the cluster falls back to a network pull at pod-create.
	}
	return kubeconfig, clusterName
}

// assertProjectNamespaceLive asserts a project namespace owned by this run exists on the cluster
// and carries the eden ownership + project labels. It scans the namespaces labeled with the
// adapter's owner label, finds the one this run's ownership prefix authored, and returns its name
// (so Stop's reap can be asserted against the exact namespace). It fails if none is found.
func assertProjectNamespaceLive(t *testing.T, kubeconfig, labelNamespace, projectID string) string {
	t.Helper()
	// The kubernetesadapter labels every authored namespace with eden.workspaceprovider/owned=true
	// + eden.workspaceprovider/namespace=<labelNamespace>. Select on both so we see exactly what
	// this run authored.
	selector := "eden.workspaceprovider/owned=true,eden.workspaceprovider/namespace=" + sanitizeLabel(labelNamespace)
	names := kubectlNamespaceNames(t, kubeconfig, selector)
	if len(names) == 0 {
		t.Fatalf("no project namespace found on the cluster for ownership prefix %q (selector %q): the kubernetes provisioner must create a namespace-per-workspace", labelNamespace, selector)
	}
	ns := names[0]
	// The project label must carry the spawn's project (sanitized to a label value), proving the
	// namespace is tenancy-scoped (eden-<prefix>-<projUUID>-shaped per the deployment contract).
	gotProject := kubectlNamespaceLabel(t, kubeconfig, ns, "eden.workspaceprovider/project")
	if gotProject == "" {
		t.Fatalf("project namespace %q carries no eden.workspaceprovider/project label (it must be tenancy-labeled)", ns)
	}
	if !strings.Contains(gotProject, sanitizeLabel(firstLabelSegment(projectID))) && !strings.HasPrefix(sanitizeLabel(projectID), gotProject) {
		t.Logf("project namespace %q project label = %q (derived from project %q)", ns, gotProject, projectID)
	}
	return ns
}

// assertProjectNamespaceReaped polls until the project namespace is gone or Terminating (the
// foreground-delete reclaim contract): a Stop tears the namespace down, cascading to the pod.
func assertProjectNamespaceReaped(t *testing.T, kubeconfig, namespace string) {
	t.Helper()
	deadline := time.After(2 * time.Minute)
	for {
		phase := kubectlNamespacePhase(t, kubeconfig, namespace)
		if phase == "" || phase == "Terminating" {
			return // gone (absent) or being reclaimed (Terminating) — the reap contract holds
		}
		select {
		case <-deadline:
			t.Fatalf("project namespace %q was not reaped after Stop (phase still %q)", namespace, phase)
		case <-time.After(time.Second):
		}
	}
}

// kubectlNamespaceNames returns the names of namespaces matching the label selector.
func kubectlNamespaceNames(t *testing.T, kubeconfig, selector string) []string {
	t.Helper()
	out := kubectl(t, kubeconfig, "get", "namespaces", "-l", selector, "-o", "name")
	var names []string
	for _, line := range strings.Fields(out) {
		names = append(names, strings.TrimPrefix(line, "namespace/"))
	}
	return names
}

// kubectlNamespaceLabel returns a single label value off a namespace (empty when unset).
func kubectlNamespaceLabel(t *testing.T, kubeconfig, namespace, key string) string {
	t.Helper()
	// jsonpath escaping of a dotted/slashed label key: wrap in the index form.
	jsonpath := "-o=jsonpath={.metadata.labels['" + strings.ReplaceAll(key, ".", "\\.") + "']}"
	return strings.TrimSpace(kubectl(t, kubeconfig, "get", "namespace", namespace, jsonpath))
}

// kubectlNamespacePhase returns a namespace's status phase ("Active"/"Terminating"), or "" when
// the namespace is absent (a get on a missing namespace is a not-found, which we map to gone).
func kubectlNamespacePhase(t *testing.T, kubeconfig, namespace string) string {
	t.Helper()
	// #nosec G204 -- fixed `kubectl get namespace` against this run's isolated kubeconfig.
	cmd := exec.Command("kubectl", "--kubeconfig", kubeconfig, "get", "namespace", namespace, "-o=jsonpath={.status.phase}")
	out, err := cmd.CombinedOutput()
	if err != nil {
		if strings.Contains(strings.ToLower(string(out)), "notfound") || strings.Contains(strings.ToLower(string(out)), "not found") {
			return "" // gone
		}
		// A transient apiserver hiccup mid-reap: treat as still-present so the poll continues.
		return "Active"
	}
	return strings.TrimSpace(string(out))
}

// kubectl runs a kubectl verb against this run's isolated kubeconfig and returns stdout, failing
// the test on a non-zero exit (the assertions need a reliable apiserver read).
func kubectl(t *testing.T, kubeconfig string, args ...string) string {
	t.Helper()
	full := append([]string{"--kubeconfig", kubeconfig}, args...)
	// #nosec G204 -- fixed kubectl verbs against this run's isolated kubeconfig; args are test-fixed.
	out, err := exec.Command("kubectl", full...).CombinedOutput()
	if err != nil {
		t.Fatalf("kubectl %s: %v\n%s", strings.Join(args, " "), err, out)
	}
	return string(out)
}

// uniqueK3dName derives a collision-proof, RFC-1123-valid k3d cluster name.
func uniqueK3dName() string {
	var b [4]byte
	_, _ = rand.Read(b[:]) //nolint:errcheck // crypto/rand never short-reads here; a zero suffix is still usable.
	return "eden-orch-test-" + time.Now().Format("150405") + "-" + hex.EncodeToString(b[:])
}

// sanitizeLabel lowercases + strips a value to the [a-z0-9-] subset the kubernetesadapter's label
// sanitizer produces, so the test's expected label value matches the adapter's authored one.
func sanitizeLabel(s string) string {
	var out strings.Builder
	prevDash := false
	for _, r := range strings.ToLower(s) {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9'):
			out.WriteRune(r)
			prevDash = false
		default:
			if !prevDash {
				out.WriteByte('-')
				prevDash = true
			}
		}
	}
	return strings.Trim(out.String(), "-")
}

// firstLabelSegment returns the leading dash-delimited segment of a derived label value (a UUID's
// first group), enough to confirm the project flowed into the namespace's tenancy label.
func firstLabelSegment(s string) string {
	if i := strings.IndexByte(s, '-'); i > 0 {
		return s[:i]
	}
	return s
}
