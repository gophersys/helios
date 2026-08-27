package codeinsight

import (
	"bufio"
	"bytes"
	"context"
	"os/exec"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// recordSeparator is the NUL-flanked record marker prefixing each commit header in the git log
// stream. RS (0x1e) cannot occur in a path or an author field, so it unambiguously frames each
// commit even when --numstat lines follow.
const recordSeparator = "\x1e"

// SystemGitHistory is the concrete History adapter: it shells the system `git` binary in one
// `git log --numstat` pass and parses the stream into Commits (the SCM substrate adapter, contract
// §2). It is the Go-native equivalent of PyDriller's Commit/ModifiedFile surface. The zero value is
// usable; construct via NewSystemGitHistory for symmetry with the rest of the hexagon.
type SystemGitHistory struct{}

// compile-time assertion: *SystemGitHistory implements the History port.
var _ History = (*SystemGitHistory)(nil)

// NewSystemGitHistory returns the system-git History adapter. It is pure: it spawns no process until
// Walk is called.
func NewSystemGitHistory() *SystemGitHistory { return &SystemGitHistory{} }

// Walk runs one `git log --no-merges --numstat` over the window and returns the commits
// (newest→oldest) plus the current HEAD hash. Merges are excluded so churn is attributed to the
// commit that authored each line, not the merge. A git failure is surfaced as a wrapped, classified
// error the caller branches on by Kind.
func (g *SystemGitHistory) Walk(ctx context.Context, repositoryPath string, window WalkWindow) ([]Commit, string, error) {
	head, err := g.head(ctx, repositoryPath)
	if err != nil {
		return nil, "", err
	}
	commits, err := g.log(ctx, repositoryPath, window)
	if err != nil {
		return nil, "", err
	}
	return commits, head, nil
}

// log runs the numstat log pass and parses it into structured commits.
func (g *SystemGitHistory) log(ctx context.Context, repositoryPath string, window WalkWindow) ([]Commit, error) {
	// NUL-delimited header fields keep author names with spaces/quotes intact; --numstat appends
	// machine-readable "added\tdeleted\tpath" lines per file.
	args := []string{
		"-C", repositoryPath,
		"log", "--no-merges", "--numstat",
		"--format=" + recordSeparator + "%H%x00%an <%ae>%x00%aI",
	}
	if window.Since != "" {
		args = append(args, "--since="+window.Since)
	}
	if window.Until != "" {
		args = append(args, "--until="+window.Until)
	}

	out, err := g.run(ctx, args)
	if err != nil {
		return nil, err
	}
	return parseLog(out), nil
}

// head returns the current HEAD hash — the commit the static snapshot is taken at.
func (g *SystemGitHistory) head(ctx context.Context, repositoryPath string) (string, error) {
	out, err := g.run(ctx, []string{"-C", repositoryPath, "rev-parse", "HEAD"})
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// run executes a git invocation and returns its stdout, mapping a failure to a classified error
// carrying NO raw stderr in the typed boundary (the chain preserves git's stderr for diagnosis).
func (g *SystemGitHistory) run(ctx context.Context, args []string) ([]byte, error) {
	if err := errors.FromContext(ctx); err != nil {
		return nil, err
	}
	var stdout, stderr bytes.Buffer
	command := exec.CommandContext(ctx, "git", args...) // #nosec G204 -- inherent exec adapter: the binary is git; args are library-shaped (a fixed verb + the bound repository path/window), never raw user input on argv, never a shell.
	command.Stdout = &stdout
	command.Stderr = &stderr
	if err := command.Run(); err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "codeinsight: git "+args[len(args)-1], err)
	}
	return stdout.Bytes(), nil
}

// parseLog turns the `git log --numstat` stream into structured commits.
func parseLog(raw []byte) []Commit {
	var commits []Commit
	var current *Commit

	scan := bufio.NewScanner(bytes.NewReader(raw))
	scan.Buffer(make([]byte, 0, 1<<20), 1<<24) // long diffstat lines on large commits
	for scan.Scan() {
		line := scan.Text()
		if strings.HasPrefix(line, recordSeparator) {
			if current != nil {
				commits = append(commits, *current)
			}
			current = parseHeader(line)
			continue
		}
		if current == nil || strings.TrimSpace(line) == "" {
			continue
		}
		if delta, ok := parseNumstat(line); ok {
			current.Changes = append(current.Changes, delta)
		}
	}
	if current != nil {
		commits = append(commits, *current)
	}
	return commits
}

// parseHeader parses a record-separator-prefixed commit header line into a Commit, or nil for a
// malformed header.
func parseHeader(line string) *Commit {
	fields := strings.Split(strings.TrimPrefix(line, recordSeparator), "\x00")
	if len(fields) != 3 {
		return nil
	}
	return &Commit{Hash: fields[0], Author: fields[1], At: fields[2]}
}

// parseNumstat parses one "added\tdeleted\tpath" line. Binary files report "-\t-" and are recorded
// with zero line churn (they still count as a change for frequency/coupling).
func parseNumstat(line string) (FileChange, bool) {
	parts := strings.SplitN(line, "\t", 3)
	if len(parts) != 3 {
		return FileChange{}, false
	}
	added, _ := strconv.Atoi(parts[0])   //nolint:errcheck // a binary file reports "-", which Atoi maps to 0 — the intended zero-churn behavior.
	deleted, _ := strconv.Atoi(parts[1]) //nolint:errcheck // see above: binary "-" → 0 deleted lines.
	path := normalizeRenamePath(parts[2])
	if path == "" {
		return FileChange{}, false
	}
	return FileChange{Path: path, Added: added, Deleted: deleted}, true
}

// normalizeRenamePath collapses git's rename notation to the destination path so a renamed file's
// history stays attached to its current location. Handles both the "a/{old => new}/c" brace form and
// the plain "old => new" form.
func normalizeRenamePath(raw string) string {
	path := strings.TrimSpace(raw)
	if open := strings.Index(path, "{"); open != -1 && strings.Contains(path[open:], "=>") {
		closeBrace := strings.Index(path, "}")
		if closeBrace > open {
			inner := path[open+1 : closeBrace]
			_, dest, _ := strings.Cut(inner, "=>")
			path = path[:open] + strings.TrimSpace(dest) + path[closeBrace+1:]
			path = strings.ReplaceAll(path, "//", "/")
		}
	} else if _, dest, found := strings.Cut(path, "=>"); found {
		path = strings.TrimSpace(dest)
	}
	return path
}
