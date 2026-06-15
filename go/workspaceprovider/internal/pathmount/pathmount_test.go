package pathmount_test

import (
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/pathmount"
)

func TestDefaultWorkDir(t *testing.T) {
	t.Parallel()
	if got := pathmount.DefaultWorkDir(&workspaceprovider.WorkspaceSpec{}); got != "/workspace" {
		t.Errorf("DefaultWorkDir(no mounts) = %q, want /workspace", got)
	}
	spec := &workspaceprovider.WorkspaceSpec{Mounts: []workspaceprovider.Mount{
		{Kind: workspaceprovider.MountTmpfs, Target: "/scratch"},
		{Kind: workspaceprovider.MountBind, Target: "/src"},
	}}
	if got := pathmount.DefaultWorkDir(spec); got != "/src" {
		t.Errorf("DefaultWorkDir = %q, want /src (first Bind/Inputs)", got)
	}
}

func TestSecretMountDirAndBaseName(t *testing.T) {
	t.Parallel()
	cases := []struct {
		target  string
		wantDir string
		wantBN  string
	}{
		{"/run/eden/secrets/token", "/run/eden/secrets", "token"},
		{"/file", "/", "file"},
		{"/a/b/", "/a", "b"},
	}
	for _, tc := range cases {
		if got := pathmount.SecretMountDir(tc.target); got != tc.wantDir {
			t.Errorf("SecretMountDir(%q) = %q, want %q", tc.target, got, tc.wantDir)
		}
		if got := pathmount.SecretBaseName(tc.target); got != tc.wantBN {
			t.Errorf("SecretBaseName(%q) = %q, want %q", tc.target, got, tc.wantBN)
		}
	}
}
