package dockeradapter

import (
	"github.com/gophersys/libs/go/workspaceprovider"
)

// handleFor builds the docker Handle for a workspace by round-tripping the canonical
// string through the library's ParseHandle (so the adapter never constructs a Handle
// out-of-band). The Handle carries substrate=docker, the namespace, the tenancy keys, the
// workspace name, and the workdir. The native container is addressed by a DETERMINISTIC
// name (containerName(spec.Name)) rather than the opaque container id, so Dial/Destroy
// re-derive the address from the Handle's Name() alone — the id need not ride the Handle,
// which keeps it stable across a recreate and survives the library's stampHandle re-derive.
func (a *Adapter) handleFor(spec *workspaceprovider.WorkspaceSpec, workDir string) workspaceprovider.Handle {
	raw := workspaceprovider.EncodeHandle(
		workspaceprovider.SubstrateDocker,
		a.namespace,
		spec.Labels[workspaceprovider.LabelOrganization],
		spec.Labels[workspaceprovider.LabelProject],
		spec.Name,
		workDir,
	)
	handle, err := workspaceprovider.ParseHandle(raw)
	if err != nil {
		// spec.Name is non-empty by the library's validateSpec before Create reaches the
		// adapter, so a malformed handle here is a programming error in this adapter.
		panic("dockeradapter: produced a malformed handle: " + err.Error())
	}
	return handle
}

// containerID returns the DETERMINISTIC docker container name this adapter assigned for the
// workspace the handle names. docker's inspect/remove/exec accept a name as well as an id,
// so the deterministic name is a stable native address that needs no extra Handle field.
// The namespace is read from the handle so a Provider reconstructed over a different
// namespace cannot address another namespace's containers.
func containerID(handle workspaceprovider.Handle) string {
	if handle.IsZero() {
		return ""
	}
	return deriveContainerName(handle.Namespace(), handle.Name())
}
