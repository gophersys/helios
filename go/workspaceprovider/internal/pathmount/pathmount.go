// Package pathmount holds the substrate-neutral path/mount derivations both adapters share: the
// default workdir selection, a MountSecret's tmpfs/secret-volume parent directory, and a
// MountSecret target's basename. These were verbatim-duplicated in dockeradapter and
// kubernetesadapter; they live ONCE here (one concept, one home — 10 §9) so a change to the
// derivation cannot drift between the two adapters.
package pathmount

import (
	"path"
	"strings"

	"github.com/gophersys/libs/go/workspaceprovider"
)

// DefaultWorkDir picks the path the harness runs in: the first Bind/Inputs mount target, else
// "/workspace". Both adapters and the library's stampHandle resolve the workdir identically.
func DefaultWorkDir(spec *workspaceprovider.WorkspaceSpec) string {
	for i := range spec.Mounts {
		if spec.Mounts[i].Kind == workspaceprovider.MountBind || spec.Mounts[i].Kind == workspaceprovider.MountInputs {
			return spec.Mounts[i].Target
		}
	}
	return "/workspace"
}

// SecretMountDir is the directory a MountSecret's tmpfs/secret volume is mounted at: the Target's
// PARENT, so the resolved secret can be written/projected as a FILE at the Target inside an
// in-memory mount. A Target with no parent (a bare "/file") mounts at "/", which still backs the
// file.
func SecretMountDir(target string) string {
	dir := path.Dir(strings.TrimRight(target, "/"))
	if dir == "" || dir == "." {
		return "/"
	}
	return dir
}

// SecretBaseName is the basename a MountSecret's resolved value is projected as inside its mount
// directory (the kubernetes secret-volume KeyToPath path / the docker tmpfs filename). It is the
// final path segment of the Target.
func SecretBaseName(target string) string {
	return path.Base(strings.TrimRight(target, "/"))
}
