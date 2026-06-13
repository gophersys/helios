package kubernetesadapter

import (
	"context"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// EphemeralConfig configures a kubernetes Adapter bound to a (test-owned) cluster under a
// dedicated ownership-domain namespace prefix, so the Cleanup reaps exactly what this run
// created. Kubeconfig/Context select the cluster (an ephemeral k3d/kind one in the test
// harness); LabelNamespace scopes the namespaces; Distro is the truthful manifest identity.
type EphemeralConfig struct {
	Kubeconfig     string
	Context        string
	LabelNamespace string
	Distro         string
}

// NewEphemeral builds a kubernetes Adapter bound to the cluster the kubeconfig selects under a
// dedicated label namespace, confirms the apiserver is reachable (returning a
// SubstrateUnavailableError the harness maps to a Skip when it is not), and returns the Adapter
// plus a cleanup that deletes every namespace this ownership domain authored (the C23
// forced-teardown discipline — it runs on failure too, and reaps a UNIQUE namespace prefix so
// parallel/abandoned runs never collide). The CLUSTER lifecycle (create/delete) is the
// harness's job, not the adapter's; this only reaps the adapter's own namespaces.
func NewEphemeral(ctx context.Context, configuration EphemeralConfig) (*Adapter, func() error, error) {
	adapter, err := New(Config{
		Kubeconfig:     configuration.Kubeconfig,
		Context:        configuration.Context,
		LabelNamespace: configuration.LabelNamespace,
	})
	if err != nil {
		return nil, nil, err
	}
	adapter.WithDistro(configuration.Distro)
	// Confirm the apiserver answers (a List over the ownership domain is a cheap reachability
	// probe that also primes the client). A failure here is mapped to a Skip by the harness.
	if _, lerr := adapter.client.ListNamespaces(ctx, metav1ListOptions(adapter.ownerSelector(nil))); lerr != nil {
		return nil, nil, errors.Wrap(errors.KindUnavailable, "kubernetesadapter.NewEphemeral: reach apiserver", lerr)
	}
	cleanup := func() error {
		return adapter.reapNamespaces(context.WithoutCancel(ctx))
	}
	return adapter, cleanup, nil
}

// reapNamespaces deletes every namespace this adapter's ownership domain authored — the Cleanup
// that guarantees zero orphans. It is idempotent (an already-gone namespace is skipped).
func (a *Adapter) reapNamespaces(ctx context.Context) error {
	nsList, err := a.client.ListNamespaces(ctx, metav1ListOptions(a.ownerSelector(nil)))
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "kubernetesadapter.reapNamespaces: list", err)
	}
	var reapErr error
	for i := range nsList.Items {
		name := nsList.Items[i].Name
		if derr := a.client.DeleteNamespace(ctx, name, foregroundDelete()); derr != nil && !isNotFound(derr) {
			reapErr = errors.Wrap(errors.KindUnavailable, "kubernetesadapter.reapNamespaces: delete "+name, derr)
		}
	}
	return reapErr
}

// CountOwned reports how many LIVE namespaces this adapter's ownership domain currently owns —
// the harness's orphan re-scan asserts this is zero after Teardown (the C23 leak check). A
// Terminating namespace is NOT counted: kubernetes' foreground delete is acknowledged the
// instant the cascade begins but the namespace lingers in Terminating for seconds while the
// apiserver reaps it — that is reclaiming, not a leak (consistent with Dial/List, which treat
// a Terminating namespace as gone). The harness's cluster-delete is the outer guarantee for the
// lingering Terminating namespaces.
func (a *Adapter) CountOwned(ctx context.Context) (int, error) {
	nsList, err := a.client.ListNamespaces(ctx, metav1ListOptions(a.ownerSelector(nil)))
	if err != nil {
		return 0, classifyAPIError("count owned", err)
	}
	live := 0
	for i := range nsList.Items {
		if !namespaceIsTerminating(&nsList.Items[i]) {
			live++
		}
	}
	return live, nil
}

// ownerSelector renders the owner-marker + namespace-prefix label selector for the
// ownership-domain reap/count scans, plus any extra label matches.
func (a *Adapter) ownerSelector(extra map[string]string) string {
	return a.labelSelector(workspaceprovider.Selector{Labels: extra})
}

// ImagePullSecretsForTest returns the workspace pod's configured ImagePullSecret names (the
// dockerconfigjson references) for the workspace the handle names — the B7 assertion that the
// kubernetes adapter actually wired Pod.Spec.ImagePullSecrets. Test-support only.
func (a *Adapter) ImagePullSecretsForTest(ctx context.Context, handle workspaceprovider.Handle) ([]string, error) {
	namespace := handleNamespace(handle)
	pod, err := a.client.GetPod(ctx, namespace, workspacePodName)
	if err != nil {
		return nil, classifyAPIError("get pod for pull-secret assertion", err)
	}
	names := make([]string, 0, len(pod.Spec.ImagePullSecrets))
	for i := range pod.Spec.ImagePullSecrets {
		names = append(names, pod.Spec.ImagePullSecrets[i].Name)
	}
	return names, nil
}

// PullSecretTypeForTest returns the kubernetes Secret type of the workspace's pull-secret object
// (kubernetes.io/dockerconfigjson when the B7 fix wired it), so a test asserts the Secret is the
// right type WITHOUT reading its value. Test-support only.
func (a *Adapter) PullSecretTypeForTest(ctx context.Context, handle workspaceprovider.Handle) (string, error) {
	namespace := handleNamespace(handle)
	secret, err := a.client.GetSecret(ctx, namespace, pullSecretObjectName)
	if err != nil {
		return "", classifyAPIError("get pull-secret for assertion", err)
	}
	return string(secret.Type), nil
}

// metav1ListOptions builds a metav1.ListOptions from a label selector string.
func metav1ListOptions(selector string) metav1.ListOptions {
	return metav1.ListOptions{LabelSelector: selector}
}
