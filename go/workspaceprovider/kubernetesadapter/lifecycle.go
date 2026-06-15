package kubernetesadapter

import (
	"context"
	"strings"
	"time"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/pathmount"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// readyPollInterval / readyTimeout bound the Ready handshake: Create waits for the pod to
// reach Running before returning a Ready Workspace (the handshake the contract requires —
// "image pulled, namespace/pod created, mounts attached, ... the handshake confirmed").
const (
	readyPollInterval = 250 * time.Millisecond
	readyTimeout      = 3 * time.Minute
)

// Create provisions the native kubernetes objects for a workspace: a labeled NAMESPACE (the
// ownership + tenancy unit), an optional default-deny NetworkPolicy derived from the
// declared egress (where the CNI enforces it), and a single long-lived POD running the hold
// command with the spec's mounts/resource-limits/env. It WAITS for the pod to be Running
// (the Ready handshake) before returning. ROLLBACK is the adapter's obligation: any partial
// failure deletes the namespace (which cascades to the pod + policy), so no orphan is left
// (the all-or-nothing contract, 07 §3). A workspace whose declared isolation cannot be
// applied is an IsolationError, never a degraded success.
//
//nolint:gocritic // contract §2 fixes Adapter.Create's spec/resolved by value; the port surface is frozen.
func (a *Adapter) Create(ctx context.Context, spec workspaceprovider.WorkspaceSpec, resolved workspaceprovider.Resolved) (workspaceprovider.HandleData, error) {
	workDir := defaultWorkDir(&spec)
	namespace := a.k8sNamespace(spec.Name)

	if cerr := a.createNamespace(ctx, &spec, namespace); cerr != nil {
		return workspaceprovider.HandleData{}, cerr
	}

	// From here every failure must roll back the namespace (cascades to all its objects).
	rollback := func(cause error) (workspaceprovider.HandleData, error) {
		_ = a.client.DeleteNamespace(context.WithoutCancel(ctx), namespace, foregroundDelete()) //nolint:errcheck // best-effort rollback; the cause error is the one returned.
		return workspaceprovider.HandleData{}, cause
	}

	if perr := a.installEgressPolicy(ctx, &spec, namespace); perr != nil {
		return rollback(perr)
	}

	// Materialize the credential seam (07 §2) as native kubernetes Secrets BEFORE the pod:
	// each MountSecret's resolved bytes become a corev1.Secret mounted at its Target (a secret
	// volume, defaultMode 0400), and a resolved pull-secret becomes a dockerconfigjson Secret
	// referenced via Pod.Spec.ImagePullSecrets. The library resolved the values server-side and
	// Zeroizes them after Create; they ride the apiserver-stored Secret object, never the pod
	// spec or a log. A failure here is fail-closed: roll back the namespace.
	creds, serr := a.createSecrets(ctx, &spec, namespace, resolved)
	if serr != nil {
		return rollback(serr)
	}

	pod, berr := buildPod(&spec, a.ownerLabels(&spec), workDir, creds)
	if berr != nil {
		return rollback(berr)
	}
	if _, cerr := a.client.CreatePod(ctx, namespace, pod); cerr != nil {
		return rollback(classifyAPIError("create pod", cerr))
	}

	if werr := a.waitReady(ctx, namespace, pod.Name); werr != nil {
		return rollback(werr)
	}

	handle := a.handleFor(&spec, namespace, workDir)
	return workspaceprovider.HandleData{
		Handle:     handle,
		Connection: a.connection(namespace, pod.Name, handle),
	}, nil
}

// createNamespace creates the labeled ownership-domain namespace. An AlreadyExists is a
// ConflictError (a non-idempotent collision — the library's findExisting handles the
// idempotent re-Provision before Create is ever reached).
func (a *Adapter) createNamespace(ctx context.Context, spec *workspaceprovider.WorkspaceSpec, namespace string) error {
	annotations := map[string]string{workdirAnnotation: defaultWorkDir(spec)}
	// The spec fingerprint is stored as an ANNOTATION (not a label): a sha256 hex digest is
	// 64 chars, over the 63-char kubernetes label-value ceiling, and annotations have no such
	// limit. List folds it back into the Descriptor's Labels so the library's idempotency/
	// conflict check reads it uniformly across substrates.
	if fp := spec.Labels[workspaceprovider.SpecFingerprintLabel]; fp != "" {
		annotations[fingerprintAnnotation] = fp
	}
	ns := &corev1.Namespace{
		ObjectMeta: metav1.ObjectMeta{
			Name:        namespace,
			Labels:      a.ownerLabels(spec),
			Annotations: annotations,
		},
	}
	if _, err := a.client.CreateNamespace(ctx, ns); err != nil {
		if apierrors.IsAlreadyExists(err) {
			return &workspaceprovider.ConflictError{Name: spec.Name}
		}
		return classifyAPIError("create namespace", err)
	}
	return nil
}

// installEgressPolicy derives a default-deny + declared-allow NetworkPolicy from the spec's
// Egress and installs it WHERE the CNI enforces it. The policy is always installed (it is
// inert on a CNI that does not enforce NetworkPolicy, e.g. flannel on k3d/kind — the
// honest CapEgressPolicy=Absent in the manifest); installing it is harmless and keeps the
// data faithful. A rejected policy (a cluster without the NetworkPolicy API) is an
// IsolationError (fail-closed: declared isolation that cannot be applied is never Ready),
// EXCEPT we tolerate the absence of the networking API entirely as a no-op so a minimal
// distro provisions without egress enforcement (the manifest already declares it absent).
func (a *Adapter) installEgressPolicy(ctx context.Context, spec *workspaceprovider.WorkspaceSpec, namespace string) error {
	policy := buildNetworkPolicy(spec, namespace)
	if policy == nil {
		return nil
	}
	if _, err := a.client.CreateNetworkPolicy(ctx, namespace, policy); err != nil {
		if apierrors.IsNotFound(err) || isNoNetworkPolicyAPI(err) {
			// The cluster does not expose the NetworkPolicy API; the manifest declares
			// CapEgressPolicy absent, so this is a no-op, not a failure.
			return nil
		}
		return &workspaceprovider.IsolationError{Handle: a.handleFor(spec, namespace, defaultWorkDir(spec)), Detail: "install egress NetworkPolicy: " + err.Error()}
	}
	return nil
}

// Dial re-attaches to an existing workspace by its handle's namespace. NotFoundError if the
// namespace (or its pod) is gone — torn down, evicted, GC'd, OR mid-deletion (Terminating):
// a foreground Teardown returns once the cascade is INITIATED, so the namespace lingers in
// Terminating for a while; a re-dial to a Terminating namespace is NotFound (the contract's
// "after Teardown, Open returns NotFoundError" — the workspace is gone the instant Teardown
// is acknowledged, not when the apiserver finishes reaping).
func (a *Adapter) Dial(ctx context.Context, handle workspaceprovider.Handle) (workspaceprovider.HandleData, error) {
	namespace := handleNamespace(handle)
	if namespace == "" {
		return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
	}
	ns, err := a.client.GetNamespace(ctx, namespace)
	if err != nil {
		if apierrors.IsNotFound(err) {
			return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
		}
		return workspaceprovider.HandleData{}, classifyAPIError("get namespace", err)
	}
	if namespaceIsTerminating(ns) {
		return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
	}
	pod, err := a.client.GetPod(ctx, namespace, workspacePodName)
	if err != nil {
		if apierrors.IsNotFound(err) {
			return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
		}
		return workspaceprovider.HandleData{}, classifyAPIError("get pod", err)
	}
	return workspaceprovider.HandleData{
		Handle:     handle,
		Connection: a.connection(namespace, pod.Name, handle),
	}, nil
}

// List enumerates the namespaces this adapter authored that match the selector's labels (the
// ownership-domain scan, 05 §5). It returns Descriptors (metadata, not live handles).
func (a *Adapter) List(ctx context.Context, selector workspaceprovider.Selector) ([]workspaceprovider.Descriptor, error) {
	nsList, err := a.client.ListNamespaces(ctx, metav1.ListOptions{LabelSelector: a.labelSelector(selector)})
	if err != nil {
		return nil, classifyAPIError("list namespaces", err)
	}
	out := make([]workspaceprovider.Descriptor, 0, len(nsList.Items))
	for i := range nsList.Items {
		ns := &nsList.Items[i]
		// A Terminating namespace is being reclaimed (a foreground Teardown is mid-cascade);
		// it is no longer part of the LIVE ownership domain, so List excludes it — the
		// reconcile loop sees it gone the instant Teardown is acknowledged, and the
		// idempotent-Teardown conformance case observes "List no longer includes it".
		if namespaceIsTerminating(ns) {
			continue
		}
		workDir := ns.Annotations[workdirAnnotation]
		descSpec := descriptorSpec(ns.Labels)
		handle := a.handleFor(&descSpec, ns.Name, workDir)
		// Fold the fingerprint annotation back into the Descriptor's Labels so the library's
		// idempotency/conflict check reads it uniformly with the docker adapter (which carries
		// it as a native label).
		descLabels := foldAnnotations(ns.Labels, ns.Annotations)
		out = append(out, workspaceprovider.Descriptor{
			Handle:    handle,
			Name:      ns.Labels[nameLabel],
			Substrate: workspaceprovider.SubstrateKubernetes,
			State:     normalizeNamespaceState(ns),
			Labels:    descLabels,
			CreatedAt: ns.CreationTimestamp.Time,
		})
	}
	return out, nil
}

// Destroy removes the namespace named by handle (cascading to its pod + policy + volumes).
// IDEMPOTENT: an already-gone namespace is nil, not an error. ctx bounds the graceful
// drain; foreground deletion blocks until the cascade is acknowledged so a subsequent Open
// observes NotFound.
func (a *Adapter) Destroy(ctx context.Context, handle workspaceprovider.Handle) error {
	namespace := handleNamespace(handle)
	if namespace == "" {
		return nil
	}
	if err := a.client.DeleteNamespace(ctx, namespace, foregroundDelete()); err != nil {
		if apierrors.IsNotFound(err) {
			return nil
		}
		return classifyAPIError("delete namespace", err)
	}
	return nil
}

// waitReady blocks until the workspace pod reports Running (the Ready handshake), or returns
// a typed error: an ImageError on an image-pull failure, an IsolationError on an
// unschedulable pod, a DeadlineError on the timeout, or a SubstrateUnavailableError on an
// apiserver fault. It polls the pod (a watch would be lighter, but polling keeps the bounded
// client seam small and the behavior deterministic for the conformance suite).
func (a *Adapter) waitReady(ctx context.Context, namespace, podName string) error {
	deadline := time.Now().Add(readyTimeout)
	for {
		pod, err := a.client.GetPod(ctx, namespace, podName)
		if err != nil {
			if apierrors.IsNotFound(err) {
				// The pod vanished mid-handshake (evicted/deleted) — treat as a substrate fault.
				return &workspaceprovider.SubstrateUnavailableError{Substrate: workspaceprovider.SubstrateKubernetes, Op: "await pod ready"}
			}
			return classifyAPIError("await pod ready", err)
		}
		ready, fault := evaluatePhase(pod)
		if fault != nil {
			return fault
		}
		if ready {
			return nil
		}
		if time.Now().After(deadline) || ctx.Err() != nil {
			return &workspaceprovider.DeadlineError{Op: "Provision: pod did not become Ready within " + readyTimeout.String()}
		}
		if serr := sleepCtx(ctx, readyPollInterval); serr != nil {
			return &workspaceprovider.DeadlineError{Op: "Provision: pod did not become Ready"}
		}
	}
}

// evaluatePhase classifies one poll of the workspace pod into (ready, fault): ready=true at a
// Running pod with all containers Ready; a fault is a terminal handshake failure (a bad
// command/image that exited, an image-pull failure, an unschedulable pod). A transient Pending
// returns (false, nil) so the caller keeps polling.
func evaluatePhase(pod *corev1.Pod) (ready bool, fault error) {
	switch pod.Status.Phase {
	case corev1.PodRunning:
		return podContainersReady(pod), nil
	case corev1.PodSucceeded, corev1.PodFailed:
		// The hold command never exits, so a Succeeded/Failed pod means a bad command/image.
		return false, &workspaceprovider.ImageError{Image: imageOf(pod)}
	case corev1.PodPending, corev1.PodUnknown:
		return false, pendingFault(pod)
	default:
		return false, nil
	}
}

// pendingFault inspects a Pending pod's container statuses for a terminal-ish fault the
// handshake must surface immediately rather than waiting out the full timeout: an
// ImagePullBackOff/ErrImagePull is an ImageError; an Unschedulable condition is an
// IsolationError (no node satisfies the resource request). A transient Pending (scheduling,
// pulling) returns nil so the poll continues.
func pendingFault(pod *corev1.Pod) error {
	for i := range pod.Status.ContainerStatuses {
		waiting := pod.Status.ContainerStatuses[i].State.Waiting
		if waiting == nil {
			continue
		}
		switch waiting.Reason {
		case "ImagePullBackOff", "ErrImagePull", "InvalidImageName":
			return &workspaceprovider.ImageError{Image: imageOf(pod)}
		}
	}
	for i := range pod.Status.Conditions {
		cond := pod.Status.Conditions[i]
		if cond.Type == corev1.PodScheduled && cond.Status == corev1.ConditionFalse && cond.Reason == corev1.PodReasonUnschedulable {
			return &workspaceprovider.IsolationError{Detail: "pod unschedulable: " + cond.Message}
		}
	}
	return nil
}

// podContainersReady reports whether every container in the pod is Ready (the Running phase
// alone can precede the readiness of the container process).
func podContainersReady(pod *corev1.Pod) bool {
	if len(pod.Status.ContainerStatuses) == 0 {
		return false
	}
	for i := range pod.Status.ContainerStatuses {
		if !pod.Status.ContainerStatuses[i].Ready {
			return false
		}
	}
	return true
}

// podCredentials carries the native kubernetes Secret references the library-resolved
// credentials materialized into (createSecrets), so buildPod/buildVolumes mount them WITHOUT
// ever seeing the plaintext: mountSecretNames maps a MountSecret Target to the corev1.Secret
// name backing it, and pullSecretName is the dockerconfigjson Secret for the private-image pull
// (empty when the image is public). The values live only in the apiserver-stored Secret
// objects; this struct carries names, never bytes.
type podCredentials struct {
	mountSecretNames map[string]string
	pullSecretName   string
}

// buildPod constructs the workspace pod: a single hold container with the spec's image, the
// mounts mapped to volumes, the resource limits, the non-secret env, the MountSecret volumes,
// and (for a private image) the ImagePullSecrets. A MountVolume the distro cannot honor for the
// declared isolation is an IsolationError (fail-closed).
//
//nolint:gocritic // podCredentials is a small value struct threaded once per Create; copying it is not a path.
func buildPod(spec *workspaceprovider.WorkspaceSpec, labels map[string]string, workDir string, creds podCredentials) (*corev1.Pod, error) {
	volumes, mounts, ierr := buildVolumes(spec, creds)
	if ierr != nil {
		return nil, ierr
	}
	resourceReqs, rerr := buildResources(spec.Resources)
	if rerr != nil {
		return nil, rerr
	}
	pod := &corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{
			Name:        workspacePodName,
			Labels:      labels,
			Annotations: map[string]string{workdirAnnotation: workDir},
		},
		Spec: corev1.PodSpec{
			RestartPolicy: corev1.RestartPolicyNever,
			Containers: []corev1.Container{{
				Name:         workspaceContainer,
				Image:        spec.Image,
				Command:      containerCommand(spec),
				WorkingDir:   workDir,
				Env:          envVars(spec.Env),
				VolumeMounts: mounts,
				Resources:    resourceReqs,
			}},
			Volumes: volumes,
		},
	}
	if creds.pullSecretName != "" {
		pod.Spec.ImagePullSecrets = []corev1.LocalObjectReference{{Name: creds.pullSecretName}}
	}
	return pod, nil
}

// buildVolumes maps the spec's Mounts onto pod volumes + volume mounts. Bind/Inputs become
// writable emptyDir volumes (the workspace's workdir + the read-only inputs root the LIBRARY
// guards); Tmpfs becomes a Memory-medium emptyDir; a MountSecret becomes a genuine SECRET
// volume (defaultMode 0400) projecting the resolved corev1.Secret's value file AT the Target —
// so reading the Target returns the secret VALUE (07 §2). A MountVolume is unsupported on the
// default distro path (CapPersistentVolume is Partial) and is an IsolationError.
//
//nolint:gocritic,gocyclo,cyclop // podCredentials is a small value struct; the per-kind dispatch is a flat 1:1 mount mapping.
func buildVolumes(spec *workspaceprovider.WorkspaceSpec, creds podCredentials) ([]corev1.Volume, []corev1.VolumeMount, error) {
	var volumes []corev1.Volume
	var mounts []corev1.VolumeMount
	seen := map[string]bool{}
	for i := range spec.Mounts {
		m := spec.Mounts[i]
		volName := volumeName(m.Target, i)
		switch m.Kind {
		case workspaceprovider.MountBind, workspaceprovider.MountInputs:
			// A writable emptyDir the Files seam (tar-over-exec) seeds/reads. The read-only
			// MountInputs guarantee is enforced by the LIBRARY's Files.Put guard on every
			// substrate (07 §4), not by the volume's mount mode (which would block the seed).
			volumes = append(volumes, corev1.Volume{Name: volName, VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}}})
			mounts = append(mounts, corev1.VolumeMount{Name: volName, MountPath: m.Target})
		case workspaceprovider.MountTmpfs:
			// An in-memory scratch: a Memory-medium emptyDir so it never hits a writable layer
			// that survives the pod (07 §2).
			volumes = append(volumes, corev1.Volume{Name: volName, VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{Medium: corev1.StorageMediumMemory}}})
			mounts = append(mounts, corev1.VolumeMount{Name: volName, MountPath: m.Target})
		case workspaceprovider.MountSecret:
			// A credential vehicle: project the resolved corev1.Secret as a read-only secret
			// volume (defaultMode 0400, owner-read-only — kubernetes secret volumes are
			// tmpfs-backed, so the value never persists past the pod, 07 §2). The volume is
			// mounted at the Target's PARENT and the single value key is projected AS the
			// Target's basename, so reading the Target returns the secret VALUE.
			secretName := creds.mountSecretNames[m.Target]
			if secretName == "" {
				return nil, nil, &workspaceprovider.IsolationError{Detail: "resolved MountSecret material missing for target " + m.Target}
			}
			mode := int32(secretFileMode)
			volumes = append(volumes, corev1.Volume{Name: volName, VolumeSource: corev1.VolumeSource{Secret: &corev1.SecretVolumeSource{
				SecretName:  secretName,
				DefaultMode: &mode,
				Items:       []corev1.KeyToPath{{Key: secretValueKey, Path: secretBaseName(m.Target)}},
			}}})
			mounts = append(mounts, corev1.VolumeMount{Name: volName, MountPath: secretMountDir(m.Target), ReadOnly: true})
		case workspaceprovider.MountVolume:
			return nil, nil, &workspaceprovider.IsolationError{Detail: "this kubernetes adapter declares CapPersistentVolume partial; a named MountVolume (PVC) requires a provisioned StorageClass and is unsupported on this path"}
		default:
			return nil, nil, &workspaceprovider.IsolationError{Detail: "unknown mount kind"}
		}
		seen[volName] = true
	}
	// Always provide the default workdir as an emptyDir if no Bind/Inputs mount targeted it,
	// so Files can seed/read it (mirrors the docker adapter's ensureDirs behavior).
	workDir := defaultWorkDir(spec)
	if !targetMounted(spec, workDir) {
		volName := volumeName(workDir, len(spec.Mounts))
		volumes = append(volumes, corev1.Volume{Name: volName, VolumeSource: corev1.VolumeSource{EmptyDir: &corev1.EmptyDirVolumeSource{}}})
		mounts = append(mounts, corev1.VolumeMount{Name: volName, MountPath: workDir})
	}
	return volumes, mounts, nil
}

// targetMounted reports whether the spec already mounts something at target.
func targetMounted(spec *workspaceprovider.WorkspaceSpec, target string) bool {
	for i := range spec.Mounts {
		if spec.Mounts[i].Target == target {
			return true
		}
	}
	return false
}

// buildResources maps the spec's Resources onto a kubernetes container ResourceRequirements
// (requests == limits so the workload is Guaranteed-QoS, the predictable-isolation posture).
// CPUMilli -> milliCPU; MemoryBytes/StorageBytes -> byte quantities; PIDs has no portable
// per-pod field in vanilla kubernetes (it is a kubelet PodPidsLimit), so it is recorded in
// the spec but not enforced here — the manifest's CapResourceLimits=Full covers cpu/memory/
// storage, the dimensions kubernetes binds.
func buildResources(r workspaceprovider.Resources) (corev1.ResourceRequirements, error) {
	requests := corev1.ResourceList{}
	limits := corev1.ResourceList{}
	if r.CPUMilli > 0 {
		q := resource.NewMilliQuantity(r.CPUMilli, resource.DecimalSI)
		requests[corev1.ResourceCPU] = *q
		limits[corev1.ResourceCPU] = *q
	}
	if r.MemoryBytes > 0 {
		q := resource.NewQuantity(r.MemoryBytes, resource.BinarySI)
		requests[corev1.ResourceMemory] = *q
		limits[corev1.ResourceMemory] = *q
	}
	if r.StorageBytes > 0 {
		q := resource.NewQuantity(r.StorageBytes, resource.BinarySI)
		requests[corev1.ResourceEphemeralStorage] = *q
		limits[corev1.ResourceEphemeralStorage] = *q
	}
	reqs := corev1.ResourceRequirements{}
	if len(requests) > 0 {
		reqs.Requests = requests
		reqs.Limits = limits
	}
	return reqs, nil
}

// buildNetworkPolicy derives a default-deny-egress + declared-allow NetworkPolicy from the
// spec. A spec with NO egress rules gets a pure default-deny policy (dial-out to nothing —
// the clean-room posture, 07 §4); a spec WITH rules gets default-deny plus an allow for each
// declared host's ports (DNS is always allowed so the workload can resolve its allowed
// hosts). Returns nil only when there is nothing to express (there always is: default-deny),
// so this returns a policy whenever the adapter should attempt enforcement.
func buildNetworkPolicy(spec *workspaceprovider.WorkspaceSpec, namespace string) *networkingv1.NetworkPolicy {
	egressRules := declaredEgressRules(spec)
	return &networkingv1.NetworkPolicy{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "eden-egress",
			Namespace: namespace,
			Labels:    map[string]string{ownerLabel: "true"},
		},
		Spec: networkingv1.NetworkPolicySpec{
			PodSelector: metav1.LabelSelector{}, // all pods in the namespace
			PolicyTypes: []networkingv1.PolicyType{networkingv1.PolicyTypeEgress},
			Egress:      egressRules,
		},
	}
}

// declaredEgressRules renders the spec's EgressRules into NetworkPolicy egress entries (plus
// an always-on DNS allow). An empty declared set yields a DNS-only allow — default-deny for
// everything else.
func declaredEgressRules(spec *workspaceprovider.WorkspaceSpec) []networkingv1.NetworkPolicyEgressRule {
	rules := []networkingv1.NetworkPolicyEgressRule{dnsEgressRule()}
	for i := range spec.Egress {
		ports := spec.Egress[i].Ports
		if len(ports) == 0 {
			ports = []int{httpsPort}
		}
		var npPorts []networkingv1.NetworkPolicyPort
		for _, p := range ports {
			port := port32(p)
			proto := corev1.ProtocolTCP
			npPorts = append(npPorts, networkingv1.NetworkPolicyPort{Protocol: &proto, Port: &port})
		}
		// A CIDR is expressed as an ipBlock; a FQDN cannot be expressed in vanilla
		// NetworkPolicy (which is IP-based) — it is recorded as a port allow with no peer
		// restriction (the broker/CNI plugin enforces FQDN egress where present). This is the
		// honest limit the manifest's CapEgressPolicy declaration acknowledges.
		rule := networkingv1.NetworkPolicyEgressRule{Ports: npPorts}
		if cidr := asCIDR(spec.Egress[i].Host); cidr != "" {
			rule.To = []networkingv1.NetworkPolicyPeer{{IPBlock: &networkingv1.IPBlock{CIDR: cidr}}}
		}
		rules = append(rules, rule)
	}
	return rules
}

// labelSelector renders the owner label plus the selector's tenancy/label matches into a
// kubernetes label selector string scoping List to this adapter's ownership domain.
func (a *Adapter) labelSelector(selector workspaceprovider.Selector) string {
	parts := []string{ownerLabel + "=true"}
	if a.namespace != "" {
		parts = append(parts, namespaceLabel+"="+labelValue(a.namespace))
	}
	for k, v := range selector.Labels {
		parts = append(parts, mapSelectorLabel(k)+"="+labelValue(v))
	}
	return strings.Join(parts, ",")
}

// mapSelectorLabel maps a caller-facing tenancy label key (eden.org / eden.project) to the
// adapter's namespace label key. An unknown key is passed through (a custom ownership label).
func mapSelectorLabel(key string) string {
	switch key {
	case workspaceprovider.LabelOrganization:
		return orgLabel
	case workspaceprovider.LabelProject:
		return projectLabel
	default:
		return key
	}
}

// descriptorSpec reconstructs the minimal spec a List entry needs to re-derive a Handle from
// its namespace labels.
func descriptorSpec(labels map[string]string) workspaceprovider.WorkspaceSpec {
	return workspaceprovider.WorkspaceSpec{
		Name: labels[nameLabel],
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: labels[orgLabel],
			workspaceprovider.LabelProject:      labels[projectLabel],
		},
	}
}

// foldAnnotations returns the namespace's labels with the spec-fingerprint annotation folded
// in under the library's SpecFingerprintLabel key, so a Descriptor carries the fingerprint in
// Labels uniformly with the docker adapter (which persists it as a native label).
func foldAnnotations(labels, annotations map[string]string) map[string]string {
	if annotations[fingerprintAnnotation] == "" {
		return labels
	}
	out := make(map[string]string, len(labels)+1)
	for k, v := range labels {
		out[k] = v
	}
	out[workspaceprovider.SpecFingerprintLabel] = annotations[fingerprintAnnotation]
	return out
}

// normalizeNamespaceState maps a namespace's phase onto a workspaceprovider State for List
// Descriptors. A Terminating namespace is Gone (it is being reclaimed).
func normalizeNamespaceState(ns *corev1.Namespace) workspaceprovider.State {
	switch ns.Status.Phase {
	case corev1.NamespaceTerminating:
		return workspaceprovider.StateGone
	default:
		return workspaceprovider.StateReady
	}
}

// namespaceIsTerminating reports whether a namespace is mid-deletion (the Terminating phase or
// a non-nil DeletionTimestamp), so Dial/List treat a torn-down-but-not-yet-reaped namespace as
// gone — the convergent answer to the contract's "after Teardown, Open returns NotFoundError"
// under kubernetes' asynchronous foreground delete.
func namespaceIsTerminating(ns *corev1.Namespace) bool {
	return ns.Status.Phase == corev1.NamespaceTerminating || ns.DeletionTimestamp != nil
}

// foregroundDelete deletes a namespace in the foreground so the call blocks until the
// cascade is acknowledged (a subsequent Open then observes NotFound — the reclaim contract).
func foregroundDelete() metav1.DeleteOptions {
	policy := metav1.DeletePropagationForeground
	return metav1.DeleteOptions{PropagationPolicy: &policy}
}

// classifyAPIError maps a client-go apiserver error onto a typed workspaceprovider error. A
// not-found is a NotFoundError; a conflict is a ConflictError; everything else from the
// apiserver is a SubstrateUnavailableError (the one retryable signal). The op names the
// failing call.
func classifyAPIError(op string, err error) error {
	switch {
	case apierrors.IsNotFound(err):
		return &workspaceprovider.NotFoundError{}
	case apierrors.IsAlreadyExists(err), apierrors.IsConflict(err):
		return &workspaceprovider.ConflictError{}
	default:
		return &workspaceprovider.SubstrateUnavailableError{Substrate: workspaceprovider.SubstrateKubernetes, Op: op}
	}
}

// isNoNetworkPolicyAPI reports whether err signals the cluster does not expose the
// NetworkPolicy API at all (a minimal distro) — tolerated as a no-op egress install.
func isNoNetworkPolicyAPI(err error) bool {
	msg := strings.ToLower(err.Error())
	return strings.Contains(msg, "could not find the requested resource") ||
		strings.Contains(msg, "no matches for kind") ||
		strings.Contains(msg, "the server could not find")
}

// imageOf returns the workspace container's image from a pod (for an ImageError, never a
// secret).
func imageOf(pod *corev1.Pod) string {
	for i := range pod.Spec.Containers {
		if pod.Spec.Containers[i].Name == workspaceContainer {
			return pod.Spec.Containers[i].Image
		}
	}
	if len(pod.Spec.Containers) > 0 {
		return pod.Spec.Containers[0].Image
	}
	return ""
}

// defaultWorkDir picks the harness workdir via the shared pathmount derivation (one concept, one
// home — identical to the docker adapter and the library's stampHandle workdir resolution).
func defaultWorkDir(spec *workspaceprovider.WorkspaceSpec) string {
	return pathmount.DefaultWorkDir(spec)
}
