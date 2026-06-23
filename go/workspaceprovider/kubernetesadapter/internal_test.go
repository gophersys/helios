// White-box tests for the kubernetesadapter's PURE logic — the translation of the one
// WorkspaceSpec vocabulary into kubernetes objects (pod/volume/resource/networkpolicy builders),
// the State normalization, the deterministic naming/handle round-trip, and the full
// Create/Dial/List/Destroy lifecycle driven against an in-memory fake apiserver. These need the
// unexported builders + the unexported kubernetesClient seam, so they live in-package; the
// black-box exported surface is covered in kubernetesadapter_test.go.
//
//nolint:testpackage // the pure builders + the bounded kubernetesClient seam are unexported by design (05 §1); white-box is the only way to unit-test the translation without a real cluster.
package kubernetesadapter

import (
	"context"
	"io"
	"strings"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/watch"
)

// fakeClient is an in-memory kubernetesClient: it models namespaces + pods so the lifecycle
// logic (Create rollback, Dial NotFound, List ownership scan, Destroy idempotency) is exercised
// without an apiserver. A pod created here is immediately Running+Ready so waitReady returns.
type fakeClient struct {
	mu           sync.Mutex
	namespaces   map[string]*corev1.Namespace
	pods         map[string]*corev1.Pod    // key: namespace/name
	secrets      map[string]*corev1.Secret // key: namespace/name
	policies     map[string]*networkingv1.NetworkPolicy
	services     map[string]*corev1.Service       // key: namespace/name (editor sidecar exposure, ADR-0027)
	ingresses    map[string]*networkingv1.Ingress // key: namespace/name (host-per-agent routing, ADR-0027)
	createNSErr  error
	createPodErr error
	execHook     func(ExecRequest) error
	watchErr     error
	lastWatch    *watch.FakeWatcher
}

func newFakeClient() *fakeClient {
	return &fakeClient{
		namespaces: map[string]*corev1.Namespace{},
		pods:       map[string]*corev1.Pod{},
		secrets:    map[string]*corev1.Secret{},
		policies:   map[string]*networkingv1.NetworkPolicy{},
		services:   map[string]*corev1.Service{},
		ingresses:  map[string]*networkingv1.Ingress{},
	}
}

func podKey(namespace, name string) string { return namespace + "/" + name }

func (f *fakeClient) CreateNamespace(_ context.Context, ns *corev1.Namespace) (*corev1.Namespace, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.createNSErr != nil {
		return nil, f.createNSErr
	}
	if _, ok := f.namespaces[ns.Name]; ok {
		return nil, apierrors.NewAlreadyExists(schema.GroupResource{Resource: "namespaces"}, ns.Name)
	}
	cp := ns.DeepCopy()
	cp.Status.Phase = corev1.NamespaceActive
	f.namespaces[ns.Name] = cp
	return cp, nil
}

func (f *fakeClient) GetNamespace(_ context.Context, name string) (*corev1.Namespace, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	ns, ok := f.namespaces[name]
	if !ok {
		return nil, apierrors.NewNotFound(schema.GroupResource{Resource: "namespaces"}, name)
	}
	return ns.DeepCopy(), nil
}

//nolint:gocritic // hugeParam: the metav1.DeleteOptions param is dictated by the kubernetesClient interface this fake implements.
func (f *fakeClient) DeleteNamespace(_ context.Context, name string, _ metav1.DeleteOptions) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, ok := f.namespaces[name]; !ok {
		return apierrors.NewNotFound(schema.GroupResource{Resource: "namespaces"}, name)
	}
	delete(f.namespaces, name)
	for k := range f.pods {
		if strings.HasPrefix(k, name+"/") {
			delete(f.pods, k)
		}
	}
	return nil
}

//nolint:gocritic // hugeParam: the metav1.ListOptions param is dictated by the kubernetesClient interface this fake implements.
func (f *fakeClient) ListNamespaces(_ context.Context, opts metav1.ListOptions) (*corev1.NamespaceList, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	want := parseSelector(opts.LabelSelector)
	out := &corev1.NamespaceList{}
	for _, ns := range f.namespaces {
		if labelsMatch(ns.Labels, want) {
			out.Items = append(out.Items, *ns.DeepCopy())
		}
	}
	return out, nil
}

func (f *fakeClient) CreatePod(_ context.Context, namespace string, pod *corev1.Pod) (*corev1.Pod, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.createPodErr != nil {
		return nil, f.createPodErr
	}
	cp := pod.DeepCopy()
	// Model an immediately-Running, Ready pod so waitReady returns without polling delays.
	cp.Status.Phase = corev1.PodRunning
	cp.Status.ContainerStatuses = []corev1.ContainerStatus{{Name: workspaceContainer, Ready: true}}
	f.pods[podKey(namespace, pod.Name)] = cp
	return cp, nil
}

func (f *fakeClient) GetPod(_ context.Context, namespace, name string) (*corev1.Pod, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	pod, ok := f.pods[podKey(namespace, name)]
	if !ok {
		return nil, apierrors.NewNotFound(schema.GroupResource{Resource: "pods"}, name)
	}
	return pod.DeepCopy(), nil
}

func (f *fakeClient) PodLogs(_ context.Context, _, _ string, _ *corev1.PodLogOptions) (io.ReadCloser, error) {
	return io.NopCloser(strings.NewReader("")), nil
}

func (f *fakeClient) CreateSecret(_ context.Context, namespace string, secret *corev1.Secret) (*corev1.Secret, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	cp := secret.DeepCopy()
	f.secrets[podKey(namespace, secret.Name)] = cp
	return cp, nil
}

func (f *fakeClient) GetSecret(_ context.Context, namespace, name string) (*corev1.Secret, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	secret, ok := f.secrets[podKey(namespace, name)]
	if !ok {
		return nil, apierrors.NewNotFound(schema.GroupResource{Resource: "secrets"}, name)
	}
	return secret.DeepCopy(), nil
}

func (f *fakeClient) CreateNetworkPolicy(_ context.Context, namespace string, policy *networkingv1.NetworkPolicy) (*networkingv1.NetworkPolicy, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	cp := policy.DeepCopy()
	f.policies[namespace] = cp
	return cp, nil
}

func (f *fakeClient) CreateService(_ context.Context, namespace string, service *corev1.Service) (*corev1.Service, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	cp := service.DeepCopy()
	f.services[podKey(namespace, service.Name)] = cp
	return cp, nil
}

func (f *fakeClient) CreateIngress(_ context.Context, namespace string, ingress *networkingv1.Ingress) (*networkingv1.Ingress, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	cp := ingress.DeepCopy()
	f.ingresses[podKey(namespace, ingress.Name)] = cp
	return cp, nil
}

//nolint:gocritic // hugeParam: the ExecRequest param is dictated by the kubernetesClient interface this fake implements.
func (f *fakeClient) Exec(_ context.Context, request ExecRequest) error {
	if f.execHook != nil {
		return f.execHook(request)
	}
	return nil
}

// WatchPods returns a FakeWatcher the test drives by Adding pod objects (the supervision white-box
// path). It records the last watcher so a test can push synthetic pod transitions and assert the
// adapter normalizes them; ctx cancellation Stops it.
//
//nolint:ireturn // implements the kubernetesClient seam: WatchPods MUST return watch.Interface (client-go's watch type).
func (f *fakeClient) WatchPods(ctx context.Context, _ string) (watch.Interface, error) {
	f.mu.Lock()
	if f.watchErr != nil {
		err := f.watchErr
		f.mu.Unlock()
		return nil, err
	}
	fw := watch.NewFake()
	f.lastWatch = fw
	f.mu.Unlock()
	// Stop the watcher when ctx is canceled so the adapter's runWatch loop drains and the test's
	// goleak check stays clean.
	go func() {
		<-ctx.Done()
		fw.Stop()
	}()
	return fw, nil
}

// parseSelector parses a "k=v,k2=v2" label selector into a map.
func parseSelector(s string) map[string]string {
	out := map[string]string{}
	if s == "" {
		return out
	}
	for _, part := range strings.Split(s, ",") {
		if k, v, ok := strings.Cut(part, "="); ok {
			out[k] = v
		}
	}
	return out
}

// labelsMatch reports whether labels contains every want entry.
func labelsMatch(labels, want map[string]string) bool {
	for k, v := range want {
		if labels[k] != v {
			return false
		}
	}
	return true
}

// fakeAdapter builds an Adapter over the fake client for a given ownership namespace.
func fakeAdapter(client *fakeClient, namespace string) *Adapter {
	return &Adapter{client: client, namespace: namespace, distro: "kubernetes (fake)", prePulled: map[string]bool{}}
}

func testSpec(name string) workspaceprovider.WorkspaceSpec {
	return workspaceprovider.WorkspaceSpec{
		Name:   name,
		Image:  "busybox:1.36",
		Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountBind, Target: "/workspace"}},
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-7",
			workspaceprovider.LabelProject:      "proj-42",
		},
	}
}

func TestCreateAuthorsNamespaceAndPod(t *testing.T) {
	t.Parallel()
	client := newFakeClient()
	adapter := fakeAdapter(client, "ns")
	data := mustCreate(t, adapter, client, "ws-1")

	// Handle round-trips through ParseHandle and carries the tenancy keys.
	if data.Handle.Organization() != "org-7" || data.Handle.Project() != "proj-42" {
		t.Errorf("Handle tenancy = %q/%q, want org-7/proj-42", data.Handle.Organization(), data.Handle.Project())
	}
	if parsed, perr := workspaceprovider.ParseHandle(data.Handle.String()); perr != nil || parsed.String() != data.Handle.String() {
		t.Errorf("ParseHandle round-trip failed: %v", perr)
	}
}

func TestDialListDestroyLifecycle(t *testing.T) {
	t.Parallel()
	client := newFakeClient()
	adapter := fakeAdapter(client, "ns")
	ctx := context.Background()
	data := mustCreate(t, adapter, client, "ws-1")

	// Dial re-attaches.
	if _, derr := adapter.Dial(ctx, data.Handle); derr != nil {
		t.Errorf("Dial: %v", derr)
	}

	// List includes it with the tenancy labels.
	descs, lerr := adapter.List(ctx, workspaceprovider.Selector{Labels: testSpec("ws-1").Labels})
	if lerr != nil {
		t.Fatalf("List: %v", lerr)
	}
	if len(descs) != 1 || descs[0].Handle.String() != data.Handle.String() {
		t.Errorf("List = %d descriptors, want exactly the provisioned one", len(descs))
	}

	// Destroy reclaims; Dial then yields NotFound; second Destroy is nil (idempotent).
	if derr := adapter.Destroy(ctx, data.Handle); derr != nil {
		t.Errorf("Destroy: %v", derr)
	}
	if _, derr := adapter.Dial(ctx, data.Handle); !isWPNotFound(derr) {
		t.Errorf("Dial after Destroy = %v, want NotFoundError", derr)
	}
	if derr := adapter.Destroy(ctx, data.Handle); derr != nil {
		t.Errorf("second Destroy must be nil (idempotent), got %v", derr)
	}
}

// mustCreate provisions ws-<name> over the fake client and asserts the namespace + pod were
// authored, returning the HandleData for further assertions.
func mustCreate(t *testing.T, adapter *Adapter, client *fakeClient, name string) workspaceprovider.HandleData {
	t.Helper()
	data, err := adapter.Create(context.Background(), testSpec(name), workspaceprovider.Resolved{})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if data.Handle.IsZero() {
		t.Fatalf("Create returned a zero Handle")
	}
	if data.Connection == nil {
		t.Fatalf("Create returned a nil Connection")
	}
	wantNS := adapter.k8sNamespace(name)
	if _, ok := client.namespaces[wantNS]; !ok {
		t.Errorf("Create did not author namespace %q", wantNS)
	}
	if _, ok := client.pods[podKey(wantNS, workspacePodName)]; !ok {
		t.Errorf("Create did not author the workspace pod")
	}
	return data
}

func TestCreateRollsBackOnPodFailure(t *testing.T) {
	t.Parallel()
	client := newFakeClient()
	client.createPodErr = apierrors.NewServiceUnavailable("apiserver down")
	adapter := fakeAdapter(client, "ns")

	_, err := adapter.Create(context.Background(), testSpec("ws-fail"), workspaceprovider.Resolved{})
	if err == nil {
		t.Fatalf("Create with a failing pod create must error")
	}
	// All-or-nothing: the namespace was rolled back, leaving no orphan.
	if len(client.namespaces) != 0 {
		t.Errorf("a failed Create left %d orphaned namespace(s)", len(client.namespaces))
	}
}

func TestCreateConflictOnExistingNamespace(t *testing.T) {
	t.Parallel()
	client := newFakeClient()
	adapter := fakeAdapter(client, "ns")
	ctx := context.Background()
	if _, err := adapter.Create(ctx, testSpec("ws-dup"), workspaceprovider.Resolved{}); err != nil {
		t.Fatalf("first Create: %v", err)
	}
	// A raw second Create (bypassing the library's idempotent findExisting) collides.
	_, err := adapter.Create(ctx, testSpec("ws-dup"), workspaceprovider.Resolved{})
	conflict, isConflict := errors.AsType[*workspaceprovider.ConflictError](err)
	if !isConflict {
		t.Errorf("second Create = %v, want ConflictError", err)
	} else if conflict.Name != "ws-dup" {
		t.Errorf("ConflictError.Name = %q, want ws-dup", conflict.Name)
	}
}

func TestBuildVolumesMapsMountKinds(t *testing.T) {
	t.Parallel()
	spec := workspaceprovider.WorkspaceSpec{
		Mounts: []workspaceprovider.Mount{
			{Kind: workspaceprovider.MountBind, Target: "/workspace"},
			{Kind: workspaceprovider.MountInputs, Target: "/inputs", ReadOnly: true},
			{Kind: workspaceprovider.MountTmpfs, Target: "/scratch"},
		},
	}
	volumes, mounts, err := buildVolumes(&spec, podCredentials{mountSecretNames: map[string]string{}})
	if err != nil {
		t.Fatalf("buildVolumes: %v", err)
	}
	if len(volumes) != len(mounts) {
		t.Fatalf("volumes (%d) and mounts (%d) length mismatch", len(volumes), len(mounts))
	}
	// The tmpfs mount must be a Memory-medium emptyDir (a credential vehicle never persists).
	var sawMemory bool
	for i := range volumes {
		if volumes[i].EmptyDir != nil && volumes[i].EmptyDir.Medium == corev1.StorageMediumMemory {
			sawMemory = true
		}
	}
	if !sawMemory {
		t.Errorf("MountTmpfs must map to a Memory-medium emptyDir")
	}
	// Every mount target is covered.
	for _, target := range []string{"/workspace", "/inputs", "/scratch"} {
		if !mountsTarget(mounts, target) {
			t.Errorf("buildVolumes did not mount %q", target)
		}
	}
}

func TestBuildVolumesRejectsPersistentVolume(t *testing.T) {
	t.Parallel()
	spec := workspaceprovider.WorkspaceSpec{Mounts: []workspaceprovider.Mount{{Kind: workspaceprovider.MountVolume, Target: "/data"}}}
	_, _, err := buildVolumes(&spec, podCredentials{mountSecretNames: map[string]string{}})
	if err == nil {
		t.Fatalf("MountVolume must be an IsolationError on this path")
	}
	isolation, isIsolation := errors.AsType[*workspaceprovider.IsolationError](err)
	if !isIsolation || isolation == nil {
		t.Errorf("MountVolume rejection = %v, want IsolationError", err)
	}
}

func TestBuildResourcesIsGuaranteedQoS(t *testing.T) {
	t.Parallel()
	reqs, err := buildResources(workspaceprovider.Resources{CPUMilli: 500, MemoryBytes: 256 << 20, StorageBytes: 1 << 30})
	if err != nil {
		t.Fatalf("buildResources: %v", err)
	}
	// requests == limits (Guaranteed QoS).
	if reqs.Requests.Cpu().MilliValue() != 500 || reqs.Limits.Cpu().MilliValue() != 500 {
		t.Errorf("cpu request/limit = %d/%d, want 500/500", reqs.Requests.Cpu().MilliValue(), reqs.Limits.Cpu().MilliValue())
	}
	if reqs.Limits.Memory().Value() != 256<<20 {
		t.Errorf("memory limit = %d, want %d", reqs.Limits.Memory().Value(), 256<<20)
	}
}

func TestBuildNetworkPolicyDefaultDenyPlusDeclared(t *testing.T) {
	t.Parallel()
	spec := workspaceprovider.WorkspaceSpec{Egress: []workspaceprovider.EgressRule{{Host: "10.0.0.0/8", Ports: []int{443}}}}
	policy := buildNetworkPolicy(&spec, "eden-ws")
	if policy == nil {
		t.Fatalf("buildNetworkPolicy returned nil")
	}
	if len(policy.Spec.PolicyTypes) != 1 || policy.Spec.PolicyTypes[0] != networkingv1.PolicyTypeEgress {
		t.Errorf("policy must be egress-only (dial-out-only is structural), got %v", policy.Spec.PolicyTypes)
	}
	// DNS allow + the declared CIDR allow.
	if len(policy.Spec.Egress) < 2 {
		t.Errorf("egress rules = %d, want DNS + declared allow", len(policy.Spec.Egress))
	}
	var sawCIDR bool
	for _, rule := range policy.Spec.Egress {
		for _, peer := range rule.To {
			if peer.IPBlock != nil && peer.IPBlock.CIDR == "10.0.0.0/8" {
				sawCIDR = true
			}
		}
	}
	if !sawCIDR {
		t.Errorf("declared CIDR egress not expressed as an ipBlock")
	}
}

func TestNormalizeProbeMapsPodPhase(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name  string
		pod   *corev1.Pod
		want  workspaceprovider.State
		cond  workspaceprovider.Condition
		hasCo bool
	}{
		{name: "running", pod: &corev1.Pod{Status: corev1.PodStatus{Phase: corev1.PodRunning}}, want: workspaceprovider.StateReady},
		{name: "pending", pod: &corev1.Pod{Status: corev1.PodStatus{Phase: corev1.PodPending}}, want: workspaceprovider.StateProvisioning},
		{name: "failed", pod: &corev1.Pod{Status: corev1.PodStatus{Phase: corev1.PodFailed}}, want: workspaceprovider.StateGone},
		{
			name: "oomkilled",
			pod: &corev1.Pod{Status: corev1.PodStatus{
				Phase: corev1.PodRunning,
				ContainerStatuses: []corev1.ContainerStatus{{
					State: corev1.ContainerState{Terminated: &corev1.ContainerStateTerminated{Reason: "OOMKilled"}},
				}},
			}},
			want: workspaceprovider.StateDegraded, cond: workspaceprovider.ConditionOOMKilled, hasCo: true,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			probe := normalizeProbe(tc.pod)
			if probe.State != tc.want {
				t.Errorf("State = %v, want %v", probe.State, tc.want)
			}
			if tc.hasCo && !hasCondition(probe.Conditions, tc.cond) {
				t.Errorf("Conditions = %v, want %v", probe.Conditions, tc.cond)
			}
		})
	}
}

func TestSanitizeNameProducesValidDNSLabel(t *testing.T) {
	t.Parallel()
	cases := map[string]string{
		"eden-org-7-ws-1":     "eden-org-7-ws-1",
		"Eden_WS/Name":        "eden-ws-name",
		"":                    "eden",
		"////":                "eden",
		"-leading-and-trail-": "leading-and-trail",
	}
	for in, want := range cases {
		if got := SanitizeName(in); got != want {
			t.Errorf("SanitizeName(%q) = %q, want %q", in, got, want)
		}
	}
	// A >63-char input is truncated to a valid label.
	long := SanitizeName(strings.Repeat("a", 200))
	if len(long) > maxDNSLabel {
		t.Errorf("SanitizeName did not truncate to %d chars: len=%d", maxDNSLabel, len(long))
	}
}

func TestHandleNamespaceRoundTrip(t *testing.T) {
	t.Parallel()
	adapter := fakeAdapter(newFakeClient(), "ns")
	spec := testSpec("ws-x")
	ns := adapter.k8sNamespace("ws-x")
	handle := adapter.handleFor(&spec, ns, "/workspace")
	if got := handleNamespace(handle); got != ns {
		t.Errorf("handleNamespace round-trip = %q, want %q", got, ns)
	}
	if handle.Substrate() != workspaceprovider.SubstrateKubernetes {
		t.Errorf("Handle.Substrate = %v, want kubernetes", handle.Substrate())
	}
	if handle.WorkDir() != "/workspace" {
		t.Errorf("Handle.WorkDir = %q, want /workspace", handle.WorkDir())
	}
}

// mountsTarget reports whether mounts include one at target.
func mountsTarget(mounts []corev1.VolumeMount, target string) bool {
	for i := range mounts {
		if mounts[i].MountPath == target {
			return true
		}
	}
	return false
}

func hasCondition(conds []workspaceprovider.Condition, want workspaceprovider.Condition) bool {
	for i := range conds {
		if conds[i] == want {
			return true
		}
	}
	return false
}

func isWPNotFound(err error) bool {
	notFound, isTyped := errors.AsType[*workspaceprovider.NotFoundError](err)
	return errors.KindOf(err) == errors.KindNotFound || (isTyped && notFound != nil)
}
