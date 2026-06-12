package main

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// options holds the parsed command-line flags shared by validate and links.
type options struct {
	dir     string
	schemas string
	json    bool
	// against, when non-empty, is the git ref the T5 transition check diffs the
	// corpus against (validate only).
	against string
}

// parseArgs parses the positional directory and the --schemas / --json /
// --against flags. Exactly one positional argument (the target directory) is
// required.
func parseArgs(args []string) (options, error) {
	var (
		opts options
		dirs []string
	)
	for i := 0; i < len(args); i++ {
		a := args[i]
		switch {
		case a == "--json":
			opts.json = true
		case a == "--schemas":
			if i+1 >= len(args) {
				return opts, fmt.Errorf("--schemas requires a directory argument")
			}
			i++
			opts.schemas = args[i]
		case strings.HasPrefix(a, "--schemas="):
			opts.schemas = strings.TrimPrefix(a, "--schemas=")
		case a == "--against":
			if i+1 >= len(args) {
				return opts, fmt.Errorf("--against requires a git-ref argument")
			}
			i++
			opts.against = args[i]
		case strings.HasPrefix(a, "--against="):
			opts.against = strings.TrimPrefix(a, "--against=")
		case strings.HasPrefix(a, "-"):
			return opts, fmt.Errorf("unknown flag %q", a)
		default:
			dirs = append(dirs, a)
		}
	}
	if len(dirs) != 1 {
		return opts, fmt.Errorf("expected exactly one target directory, got %d", len(dirs))
	}
	opts.dir = dirs[0]
	info, err := os.Stat(opts.dir)
	if err != nil {
		return opts, fmt.Errorf("target %q: %w", opts.dir, err)
	}
	if !info.IsDir() {
		return opts, fmt.Errorf("target %q is not a directory", opts.dir)
	}
	return opts, nil
}

// resolveSchemaDir picks the schema directory: the explicit --schemas flag when
// given, otherwise the repo's schemas/document/v1 located by walking up from the
// target directory (and finally the current working directory) looking for it.
func resolveSchemaDir(explicit, targetDir string) (string, error) {
	if explicit != "" {
		info, err := os.Stat(explicit)
		if err != nil {
			return "", fmt.Errorf("schema dir %q: %w", explicit, err)
		}
		if !info.IsDir() {
			return "", fmt.Errorf("schema dir %q is not a directory", explicit)
		}
		return explicit, nil
	}
	const rel = "schemas/document/v1"
	for _, start := range []string{targetDir, "."} {
		abs, err := filepath.Abs(start)
		if err != nil {
			continue
		}
		if dir := findUpward(abs, rel); dir != "" {
			return dir, nil
		}
	}
	return "", fmt.Errorf("could not locate %s; pass --schemas explicitly", rel)
}

// findUpward walks from start up to the filesystem root, returning the first
// ancestor that contains the relative path rel (as a directory).
func findUpward(start, rel string) string {
	dir := start
	for {
		candidate := filepath.Join(dir, rel)
		if info, err := os.Stat(candidate); err == nil && info.IsDir() {
			return candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return ""
		}
		dir = parent
	}
}

// walkDocuments returns every document file under dir (recursively), in stable
// sorted order, excluding schema files.
func walkDocuments(dir string) ([]string, error) {
	var paths []string
	err := filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if strings.HasSuffix(d.Name(), ".schema.json") {
			return nil
		}
		if projection.IsDocumentFile(path) {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("walk %s: %w", dir, err)
	}
	sort.Strings(paths)
	return paths, nil
}

// relPath renders path relative to baseDir for compact diagnostics, falling back
// to the original path when a relative form cannot be computed.
func relPath(baseDir, path string) string {
	rel, err := filepath.Rel(baseDir, path)
	if err != nil {
		return path
	}
	return rel
}
