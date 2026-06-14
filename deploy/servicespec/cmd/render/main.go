// Command render writes the Eden deploy artifacts from the typed ServiceSpec catalog (ADR-0022 #2):
// the production Helm chart (deploy/plane/production/chart) AND the local platform compose overlay
// (deploy/plane/local/platform.yaml) — ONE source of truth, both targets, no hand-maintained drift.
//
//	go run ./cmd/render                                   # default registry/tag/namespace
//	go run ./cmd/render -registry ghcr.io/gophersys/eden -tag 1.2.3 -namespace eden
//
// It writes ONLY generated, value-free manifests (image references, env NAMES, Secret references) —
// never a credential value (those are seeded into Vault / created as kubernetes Secrets out-of-band).
package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/gophersys/eden/deploy/servicespec"
)

func main() {
	registry := flag.String("registry", "ghcr.io/gophersys/eden", "production image registry prefix")
	tag := flag.String("tag", "latest", "production image tag (a release version or a git sha)")
	namespace := flag.String("namespace", "eden", "kubernetes namespace")
	outDir := flag.String("out", "", "output root (default: the deploy/ dir relative to this command)")
	flag.Parse()

	root, err := resolveOutRoot(*outDir)
	if err != nil {
		fmt.Fprintln(os.Stderr, "render: "+err.Error())
		os.Exit(1)
	}

	services := servicespec.Catalog()

	// Production: the Helm chart.
	helmTarget := servicespec.RenderTarget{Plane: servicespec.PlaneProduction, Registry: *registry, Tag: *tag, Namespace: *namespace}
	chartRoot := filepath.Join(root, "plane", "production", "chart")
	for _, f := range servicespec.RenderHelm(helmTarget, services) {
		if err := writeFile(filepath.Join(chartRoot, f.Path), f.Content); err != nil {
			fmt.Fprintln(os.Stderr, "render helm: "+err.Error())
			os.Exit(1)
		}
	}

	// Local: the platform compose overlay (composed WITH the supporting-stack compose).
	composeTarget := servicespec.RenderTarget{Plane: servicespec.PlaneLocal}
	composeOut := filepath.Join(root, "plane", "local", "platform.yaml")
	if err := writeFile(composeOut, servicespec.RenderCompose(composeTarget, services)); err != nil {
		fmt.Fprintln(os.Stderr, "render compose: "+err.Error())
		os.Exit(1)
	}

	fmt.Printf("rendered %d services → %s (helm) + %s (compose overlay)\n", len(services), chartRoot, composeOut)
}

// resolveOutRoot returns the deploy/ root to write under. When -out is empty it derives it from the
// command's own location (deploy/servicespec/cmd/render → up three to deploy/).
func resolveOutRoot(out string) (string, error) {
	if out != "" {
		return out, nil
	}
	wd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	// When run via `go run ./cmd/render` from deploy/servicespec, wd is deploy/servicespec.
	// Walk up to the deploy/ directory.
	dir := wd
	for i := 0; i < 5; i++ {
		if filepath.Base(dir) == "deploy" {
			return dir, nil
		}
		dir = filepath.Dir(dir)
	}
	// Fall back to a deploy/ sibling of the servicespec module.
	return filepath.Join(wd, ".."), nil
}

func writeFile(path, content string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(content), 0o644) //nolint:gosec // generated, value-free manifests are world-readable by design
}
