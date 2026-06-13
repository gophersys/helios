package kubernetesadapter

import (
	"context"
	"io"
	"net/http"

	"github.com/gophersys/libs/go/errors"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/kubernetes/scheme"
	"k8s.io/client-go/rest"
	remotecommand "k8s.io/client-go/tools/remotecommand"
)

// kubernetesClient is the narrow slice of client-go this adapter uses. Naming it as an
// interface keeps the SDK surface bounded, makes the adapter's apiserver calls auditable in
// one place, and lets a unit test substitute a recording double without a cluster. The real
// clientWrapper satisfies it. It is NOT a port (the <=5-method rule is for consumer-facing
// ports): it is the bounded SDK seam — every method is one apiserver interaction the adapter
// genuinely makes, so the count reflects the substrate's real surface, not bloat.
//
//nolint:interfacebloat // not a port: the bounded client-go seam this adapter calls; each method is a real apiserver interaction.
type kubernetesClient interface {
	CreateNamespace(ctx context.Context, ns *corev1.Namespace) (*corev1.Namespace, error)
	GetNamespace(ctx context.Context, name string) (*corev1.Namespace, error)
	DeleteNamespace(ctx context.Context, name string, opts metav1.DeleteOptions) error
	ListNamespaces(ctx context.Context, opts metav1.ListOptions) (*corev1.NamespaceList, error)

	CreatePod(ctx context.Context, namespace string, pod *corev1.Pod) (*corev1.Pod, error)
	GetPod(ctx context.Context, namespace, name string) (*corev1.Pod, error)
	PodLogs(ctx context.Context, namespace, name string, opts *corev1.PodLogOptions) (io.ReadCloser, error)

	// CreateSecret creates a corev1.Secret (a MountSecret's resolved material, or the
	// dockerconfigjson pull-secret) in the workspace namespace. The value rides the Secret
	// object the apiserver stores encrypted-at-rest; it never enters the pod spec or a log.
	CreateSecret(ctx context.Context, namespace string, secret *corev1.Secret) (*corev1.Secret, error)
	// GetSecret reads a Secret's metadata/type back (test-support assertions; the value is not
	// read by the adapter).
	GetSecret(ctx context.Context, namespace, name string) (*corev1.Secret, error)

	CreateNetworkPolicy(ctx context.Context, namespace string, policy *networkingv1.NetworkPolicy) (*networkingv1.NetworkPolicy, error)

	// Exec runs a command in a pod's container over the SPDY exec plane, streaming
	// stdin/stdout/stderr. It is the kubectl-exec primitive Run/Exec/Files (tar) ride on.
	Exec(ctx context.Context, request ExecRequest) error
}

// ExecRequest is the bounded input to a pod exec: which pod/container, the command, the
// optional streams, and whether a TTY is allocated.
type ExecRequest struct {
	Namespace string
	Pod       string
	Container string
	Command   []string
	Stdin     io.Reader
	Stdout    io.Writer
	Stderr    io.Writer
	TTY       bool
}

// clientWrapper is the concrete kubernetesClient over a real client-go clientset + REST
// config. It is the ONE place a real apiserver call is made; the adapter drives the substrate
// only through this seam.
//
// The methods deliberately return the RAW client-go error UN-wrapped: the adapter layer
// (lifecycle.go / connection.go) inspects it with apierrors.IsNotFound / IsAlreadyExists /
// IsConflict and only THEN maps it to a typed Eden error (NotFoundError / ConflictError /
// SubstrateUnavailableError). Wrapping here would hide the typed apiserver classification the
// adapter must read — so wrapcheck is suppressed at this bounded SDK seam (each map is an
// auditable single apiserver call), exactly the "wrong-for-contract" carve-out the gate allows.
// hugeParam is likewise suppressed: the metav1 option structs and ExecRequest mirror client-go's
// own value-passing convention; copying a request struct once per apiserver call is not a path.
type clientWrapper struct {
	clientset  kubernetes.Interface
	restConfig *rest.Config
}

// Static assertion: clientWrapper satisfies the bounded client seam.
var _ kubernetesClient = clientWrapper{}

func (c clientWrapper) CreateNamespace(ctx context.Context, ns *corev1.Namespace) (*corev1.Namespace, error) {
	return c.clientset.CoreV1().Namespaces().Create(ctx, ns, metav1.CreateOptions{}) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

func (c clientWrapper) GetNamespace(ctx context.Context, name string) (*corev1.Namespace, error) {
	return c.clientset.CoreV1().Namespaces().Get(ctx, name, metav1.GetOptions{}) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

//nolint:gocritic // hugeParam: metav1.DeleteOptions mirrors client-go's value-passing convention; the seam copies it once per delete call.
func (c clientWrapper) DeleteNamespace(ctx context.Context, name string, opts metav1.DeleteOptions) error {
	return c.clientset.CoreV1().Namespaces().Delete(ctx, name, opts) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

//nolint:gocritic // hugeParam: metav1.ListOptions mirrors client-go's value-passing convention; the seam copies it once per list call.
func (c clientWrapper) ListNamespaces(ctx context.Context, opts metav1.ListOptions) (*corev1.NamespaceList, error) {
	return c.clientset.CoreV1().Namespaces().List(ctx, opts) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

func (c clientWrapper) CreatePod(ctx context.Context, namespace string, pod *corev1.Pod) (*corev1.Pod, error) {
	return c.clientset.CoreV1().Pods(namespace).Create(ctx, pod, metav1.CreateOptions{}) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

func (c clientWrapper) GetPod(ctx context.Context, namespace, name string) (*corev1.Pod, error) {
	return c.clientset.CoreV1().Pods(namespace).Get(ctx, name, metav1.GetOptions{}) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

func (c clientWrapper) PodLogs(ctx context.Context, namespace, name string, opts *corev1.PodLogOptions) (io.ReadCloser, error) {
	return c.clientset.CoreV1().Pods(namespace).GetLogs(name, opts).Stream(ctx) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

func (c clientWrapper) CreateSecret(ctx context.Context, namespace string, secret *corev1.Secret) (*corev1.Secret, error) {
	return c.clientset.CoreV1().Secrets(namespace).Create(ctx, secret, metav1.CreateOptions{}) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

func (c clientWrapper) GetSecret(ctx context.Context, namespace, name string) (*corev1.Secret, error) {
	return c.clientset.CoreV1().Secrets(namespace).Get(ctx, name, metav1.GetOptions{}) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

func (c clientWrapper) CreateNetworkPolicy(ctx context.Context, namespace string, policy *networkingv1.NetworkPolicy) (*networkingv1.NetworkPolicy, error) {
	return c.clientset.NetworkingV1().NetworkPolicies(namespace).Create(ctx, policy, metav1.CreateOptions{}) //nolint:wrapcheck // bounded SDK seam: the adapter inspects+maps the raw apiserver error.
}

// Exec builds the SPDY exec request against the pod's container and streams it. It is the single
// low-level exec the Run/Exec/Files seams all funnel through.
//
//nolint:gocritic // hugeParam: ExecRequest carries the streams + command; the seam copies it once per exec call, not a path.
func (c clientWrapper) Exec(ctx context.Context, request ExecRequest) error {
	req := c.clientset.CoreV1().RESTClient().Post().
		Resource("pods").
		Name(request.Pod).
		Namespace(request.Namespace).
		SubResource("exec").
		VersionedParams(&corev1.PodExecOptions{
			Container: request.Container,
			Command:   request.Command,
			Stdin:     request.Stdin != nil,
			Stdout:    request.Stdout != nil,
			Stderr:    request.Stderr != nil,
			TTY:       request.TTY,
		}, scheme.ParameterCodec)

	executor, err := remotecommand.NewSPDYExecutor(c.restConfig, http.MethodPost, req.URL())
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "kubernetesadapter: build SPDY executor", err)
	}
	return executor.StreamWithContext(ctx, remotecommand.StreamOptions{ //nolint:wrapcheck // bounded SDK seam: the adapter's classifyExec inspects the raw exec.CodeExitError.
		Stdin:  request.Stdin,
		Stdout: request.Stdout,
		Stderr: request.Stderr,
		Tty:    request.TTY,
	})
}
