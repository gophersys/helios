package codeinsighttest

import (
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// TestingT is the minimal testing surface the fixture builder needs (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
	TempDir() string
}

// RepoSeed describes an initial repository for NewRealRepo — deterministic so an analysis is
// reproducible. Commits are applied in order with the per-commit author and a synthesized authored
// time, so the temporal metrics (age, trend, ownership) are well-defined.
type RepoSeed struct {
	// DefaultBranch is the initial branch; "" means "main".
	DefaultBranch string
	// Commits are applied in order onto the default branch.
	Commits []SeedCommit
}

// SeedCommit is one commit to apply during seeding.
type SeedCommit struct {
	// Files are written (path → content) before the commit.
	Files map[string]string
	// Message is the commit message.
	Message string
	// Author is the "Name <email>" identity stamped on the commit; "" uses a default seed identity.
	Author string
	// At is the authored time; the zero value synthesizes a deterministic time spaced by index.
	At time.Time
}

// NewRealRepo materializes a REAL on-disk git repository in t.TempDir(), seeds it from RepoSeed, and
// returns its absolute root. It needs only a git binary, NO running cluster — the integration
// substrate for codeinsight is "go git" (contract §7). The seeded commits drive the analyzer's
// behavioral metrics against a genuine history, never a mocked git.
func NewRealRepo(t TestingT, seed RepoSeed) string {
	t.Helper()
	dir := t.TempDir()

	defaultBranch := seed.DefaultBranch
	if defaultBranch == "" {
		defaultBranch = "main"
	}
	runGit(t, dir, nil, "init", "-q", "-b", defaultBranch)
	runGit(t, dir, nil, "config", "user.name", "Eden Seed")
	runGit(t, dir, nil, "config", "user.email", "seed@eden.dev")

	for index := range seed.Commits {
		applySeedCommit(t, dir, index, seed.Commits[index])
	}
	return dir
}

// applySeedCommit writes one seed commit's files and records it with its author + authored time.
func applySeedCommit(t TestingT, dir string, index int, sc SeedCommit) {
	t.Helper()
	for path, content := range sc.Files {
		full := filepath.Join(dir, path)
		if mkErr := os.MkdirAll(filepath.Dir(full), 0o750); mkErr != nil {
			t.Errorf("NewRealRepo: mkdir %s: %v", filepath.Dir(full), mkErr)
			return
		}
		if wErr := os.WriteFile(full, []byte(content), 0o600); wErr != nil {
			t.Errorf("NewRealRepo: write %s: %v", full, wErr)
			return
		}
	}
	runGit(t, dir, nil, "add", "-A")

	name, email := splitAuthor(sc.Author)
	when := sc.At
	if when.IsZero() {
		when = epoch.Add(time.Duration(index) * time.Hour)
	}
	stamp := when.Format(time.RFC3339)
	env := []string{
		"GIT_AUTHOR_NAME=" + name, "GIT_AUTHOR_EMAIL=" + email,
		"GIT_COMMITTER_NAME=" + name, "GIT_COMMITTER_EMAIL=" + email,
		"GIT_AUTHOR_DATE=" + stamp, "GIT_COMMITTER_DATE=" + stamp,
	}
	runGit(t, dir, env, "commit", "-q", "--allow-empty", "-m", sc.Message)
}

// splitAuthor splits a "Name <email>" identity into its parts, falling back to a default seed
// identity for an empty author.
func splitAuthor(author string) (name, email string) {
	if author == "" {
		return "Eden Seed", "seed@eden.dev"
	}
	open := indexByte(author, '<')
	closeAngle := indexByte(author, '>')
	if open < 0 || closeAngle < open {
		return author, "unknown@eden.dev"
	}
	name = trimSpace(author[:open])
	email = author[open+1 : closeAngle]
	if name == "" {
		name = "Eden Seed"
	}
	return name, email
}

// headOf reads the HEAD commit hash of the seeded repository (the commit the static snapshot is
// taken at), failing the test on error.
func headOf(t TestingT, dir string) string {
	t.Helper()
	command := exec.Command("git", "-C", dir, "rev-parse", "HEAD") // #nosec G204 -- dir is the test's own t.TempDir(); the verb is fixed, never user input.
	command.Env = seedEnv()
	out, err := command.Output()
	if err != nil {
		t.Errorf("headOf: git rev-parse HEAD: %v", err)
		return ""
	}
	return trimSpace(string(out))
}

// runGit runs a git command in dir for the seed harness, failing the test on error. It is the
// harness's own git driver, independent of the library, so the seed is established before the
// analyzer touches the repo.
func runGit(t TestingT, dir string, env []string, args ...string) {
	t.Helper()
	command := exec.Command("git", args...) // #nosec G204 -- harness args are test-literal; never user input.
	command.Dir = dir
	command.Env = append(seedEnv(), env...)
	if out, err := command.CombinedOutput(); err != nil {
		t.Errorf("git %v: %v: %s", args, err, out)
	}
}

// seedEnv pins a deterministic, isolated environment for the harness git (no user config, no
// credential prompt).
func seedEnv() []string {
	env := []string{
		"GIT_TERMINAL_PROMPT=0",
		"GIT_CONFIG_NOSYSTEM=1",
		"GIT_CONFIG_GLOBAL=/dev/null",
		"LC_ALL=C",
	}
	if path := os.Getenv("PATH"); path != "" {
		env = append(env, "PATH="+path)
	}
	if home := os.Getenv("HOME"); home != "" {
		env = append(env, "HOME="+home)
	}
	return env
}

// indexByte returns the index of the first b in s, or -1.
func indexByte(s string, b byte) int {
	for i := 0; i < len(s); i++ {
		if s[i] == b {
			return i
		}
	}
	return -1
}

// trimSpace trims leading/trailing ASCII whitespace (space, tab, newline, carriage return) from s.
func trimSpace(s string) string {
	isSpace := func(b byte) bool { return b == ' ' || b == '\t' || b == '\n' || b == '\r' }
	start, end := 0, len(s)
	for start < end && isSpace(s[start]) {
		start++
	}
	for end > start && isSpace(s[end-1]) {
		end--
	}
	return s[start:end]
}
