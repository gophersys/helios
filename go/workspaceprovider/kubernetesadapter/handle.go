package kubernetesadapter

import (
	"strings"

	"github.com/gophersys/libs/go/workspaceprovider"
)

// workspacePodName is the DETERMINISTIC name of the single workspace pod in a workspace's
// namespace. Because the namespace already scopes the workspace 1:1, the pod name is constant
// — Dial/Destroy address the pod by (namespace, workspacePodName) with no extra Handle field,
// so the native address round-trips from the Handle's Namespace() alone.
const workspacePodName = "workspace"

// handleFor builds the kubernetes Handle for a workspace by round-tripping the canonical string
// through the library's ParseHandle (so the adapter never constructs a Handle out-of-band). The
// Handle carries substrate=kubernetes, the kubernetes namespace (the native ownership-domain
// address), the tenancy keys, the workspace name, and the workdir. The native pod is addressed
// by (namespace, workspacePodName), so Dial/Destroy re-derive the address from the Handle's
// Namespace() alone — stable across a control-plane restart (CapReattach).
func (a *Adapter) handleFor(spec *workspaceprovider.WorkspaceSpec, namespace, workDir string) workspaceprovider.Handle {
	raw := string(workspaceprovider.SubstrateKubernetes) + "://" + joinSegments(
		namespace,
		spec.Labels[workspaceprovider.LabelOrganization],
		spec.Labels[workspaceprovider.LabelProject],
		spec.Name,
		workDir,
	)
	handle, err := workspaceprovider.ParseHandle(raw)
	if err != nil {
		// spec.Name is non-empty by the library's validateSpec before Create reaches the
		// adapter, so a malformed handle here is a programming error in this adapter.
		panic("kubernetesadapter: produced a malformed handle: " + err.Error())
	}
	return handle
}

// handleNamespace returns the DETERMINISTIC kubernetes namespace this adapter assigned for the
// workspace the handle names. The library stamps the adapter-assigned namespace into the
// Handle at Provision, so a stateless re-dial (Dial) reads it straight back — there is no need
// to re-derive from (ownershipNamespace, name) here, which keeps Dial correct even when the
// Provider that re-dials was constructed with a different Config.Namespace.
func handleNamespace(handle workspaceprovider.Handle) string {
	if handle.IsZero() {
		return ""
	}
	return handle.Namespace()
}

// joinSegments percent-encodes and joins the canonical Handle path segments. It mirrors the
// library's internal encoding (only "/" and "%" are escaped) so ParseHandle round-trips a
// workdir like "/workspace" exactly.
func joinSegments(segments ...string) string {
	encoded := make([]string, len(segments))
	for i, s := range segments {
		encoded[i] = encodeSegment(s)
	}
	return strings.Join(encoded, "/")
}

// encodeSegment escapes "/" and "%" so a segment is safe inside the "/"-joined canonical Handle
// form (it mirrors the library's encodeSegment so the round-trip is exact).
func encodeSegment(s string) string {
	if !strings.ContainsAny(s, "/%") {
		return s
	}
	var b strings.Builder
	b.Grow(len(s) + 2)
	for i := 0; i < len(s); i++ {
		switch s[i] {
		case '%':
			b.WriteString("%25")
		case '/':
			b.WriteString("%2F")
		default:
			b.WriteByte(s[i])
		}
	}
	return b.String()
}
