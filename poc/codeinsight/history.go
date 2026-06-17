package codeinsight

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
)

// commit is one mined revision: identity + the per-file line deltas it introduced.
type commit struct {
	hash      string
	authorKey string // "Name <email>" — the ownership identity
	dateISO   string
	changes   []fileDelta
}

// fileDelta is one file touched by a commit, with its added/deleted line counts.
type fileDelta struct {
	path    string
	added   int
	deleted int
}

// historyOptions selects the slice of history to mine.
type historyOptions struct {
	since string // git --since value, e.g. "2026-01-01" or "3 months ago"; empty = all
	until string
}

// mineHistory walks the repository log (newest→oldest) and returns the commits in the
// window. It is the Go-native equivalent of PyDriller's Commit/ModifiedFile surface
// (research §3): one `git log --numstat` pass, parsed into structured deltas. Merges are
// excluded so churn is attributed to the commit that authored each line, not the merge.
func mineHistory(ctx context.Context, repoPath string, options historyOptions) ([]commit, error) {
	// NUL-delimited header fields keep author names with spaces/quotes intact; --numstat
	// appends machine-readable "added\tdeleted\tpath" lines per file.
	const recordSeparator = "\x1e"
	args := []string{
		"-C", repoPath,
		"log", "--no-merges", "--numstat",
		"--format=" + recordSeparator + "%H%x00%an <%ae>%x00%aI",
	}
	if options.since != "" {
		args = append(args, "--since="+options.since)
	}
	if options.until != "" {
		args = append(args, "--until="+options.until)
	}

	var stdout, stderr bytes.Buffer
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("git log: %w: %s", err, strings.TrimSpace(stderr.String()))
	}

	return parseLog(stdout.Bytes(), recordSeparator), nil
}

// parseLog turns the `git log --numstat` stream into structured commits.
func parseLog(raw []byte, recordSeparator string) []commit {
	var commits []commit
	var current *commit

	scanner := bufio.NewScanner(bytes.NewReader(raw))
	scanner.Buffer(make([]byte, 0, 1<<20), 1<<24) // long diffstat lines on large commits
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, recordSeparator) {
			if current != nil {
				commits = append(commits, *current)
			}
			fields := strings.Split(strings.TrimPrefix(line, recordSeparator), "\x00")
			if len(fields) != 3 {
				current = nil
				continue
			}
			current = &commit{hash: fields[0], authorKey: fields[1], dateISO: fields[2]}
			continue
		}
		if current == nil || strings.TrimSpace(line) == "" {
			continue
		}
		if delta, ok := parseNumstat(line); ok {
			current.changes = append(current.changes, delta)
		}
	}
	if current != nil {
		commits = append(commits, *current)
	}
	return commits
}

// parseNumstat parses one "added\tdeleted\tpath" line. Binary files report "-\t-" and
// are recorded with zero line churn (they still count as a change for frequency/coupling).
func parseNumstat(line string) (fileDelta, bool) {
	parts := strings.SplitN(line, "\t", 3)
	if len(parts) != 3 {
		return fileDelta{}, false
	}
	added, _ := strconv.Atoi(parts[0]) // "-" → 0, the intended binary-file behavior
	deleted, _ := strconv.Atoi(parts[1])
	path := normalizeRenamePath(parts[2])
	if path == "" {
		return fileDelta{}, false
	}
	return fileDelta{path: path, added: added, deleted: deleted}, true
}

// normalizeRenamePath collapses git's rename notation to the destination path so a renamed
// file's history stays attached to its current location. Handles both "a/{old => new}/c"
// brace form and the plain "old => new" form.
func normalizeRenamePath(raw string) string {
	path := strings.TrimSpace(raw)
	if open := strings.Index(path, "{"); open != -1 && strings.Contains(path[open:], "=>") {
		close := strings.Index(path, "}")
		if close > open {
			inner := path[open+1 : close]
			_, dest, _ := strings.Cut(inner, "=>")
			path = path[:open] + strings.TrimSpace(dest) + path[close+1:]
			path = strings.ReplaceAll(path, "//", "/")
		}
	} else if _, dest, found := strings.Cut(path, "=>"); found {
		path = strings.TrimSpace(dest)
	}
	return path
}

// headCommit returns the current HEAD hash — the commit the static snapshot is taken at.
func headCommit(ctx context.Context, repoPath string) (string, error) {
	var stdout, stderr bytes.Buffer
	cmd := exec.CommandContext(ctx, "git", "-C", repoPath, "rev-parse", "HEAD")
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("git rev-parse HEAD: %w: %s", err, strings.TrimSpace(stderr.String()))
	}
	return strings.TrimSpace(stdout.String()), nil
}
