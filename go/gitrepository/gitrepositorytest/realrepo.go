package gitrepositorytest

import (
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/gophersys/libs/go/gitrepository"
)

// fixedClock is a deterministic gitrepository.Clock for tests: Now() always returns a frozen
// instant so a commit's timestamps are reproducible. It keeps the test module free of the
// dependencies library.
type fixedClock struct{ at time.Time }

func (c fixedClock) Now() time.Time { return c.at }

// epoch is the frozen instant the fixed clock reports.
var epoch = time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC)

// RepoSeed describes an initial repository (branches, commits, an identity) for NewRealRepo —
// deterministic so a worktree-isolation or ff-only test is reproducible.
type RepoSeed struct {
	// DefaultBranch is the initial branch; "" means "main".
	DefaultBranch string
	// Commits are applied in order onto their target branch.
	Commits []SeedCommit
	// Identity stamps the seed commits; a zero Identity uses a default platform actor.
	Identity gitrepository.Identity
}

// SeedCommit is one commit to apply during seeding.
type SeedCommit struct {
	// Files are written (path → content) before the commit.
	Files map[string]string
	// Message is the commit message.
	Message string
	// Branch is the target branch; "" means the seed's DefaultBranch.
	Branch string
}

// NewRealRepo materializes a REAL on-disk git repository in t.TempDir() (the integration arm,
// C23: "Go tests must spin up real repos"), seeded from RepoSeed, and returns its dir + a real
// *gitrepository.Repository wired to the system git. Cleanup is registered on t. It needs only
// a git binary, NO running cluster. The returned Repository has a deterministic Clock and a
// fake secrets.Provider; consumers needing credentials seed their own.
//
//nolint:gocritic // contract §3: NewRealRepo(t, seed) is the frozen harness signature; RepoSeed is a plain copyable fixture.
func NewRealRepo(t TestingT, seed RepoSeed) (dir string, repository *gitrepository.Repository) {
	t.Helper()
	dir = t.TempDir()

	defaultBranch := seed.DefaultBranch
	if defaultBranch == "" {
		defaultBranch = "main"
	}

	runGit(t, dir, nil, "init", "-q", "-b", defaultBranch)
	// Pin a deterministic local identity for any commit not otherwise stamped.
	runGit(t, dir, nil, "config", "user.name", "Eden Seed")
	runGit(t, dir, nil, "config", "user.email", "seed@eden.dev")

	identity := seed.Identity
	if identity.IsZero() {
		identity = gitrepository.Identity{Name: "Eden Seed", Email: "seed@eden.dev", Kind: gitrepository.ActorPlatform}
	}

	for _, sc := range seed.Commits {
		branch := sc.Branch
		if branch == "" {
			branch = defaultBranch
		}
		if branch != currentBranch(t, dir) {
			runGit(t, dir, nil, "checkout", "-q", "-B", branch)
		}
		for path, content := range sc.Files {
			full := filepath.Join(dir, path)
			if mkErr := os.MkdirAll(filepath.Dir(full), 0o755); mkErr != nil {
				t.Errorf("NewRealRepo: mkdir %s: %v", filepath.Dir(full), mkErr)
				return dir, nil
			}
			if wErr := os.WriteFile(full, []byte(content), 0o644); wErr != nil { //nolint:gosec // seed fixtures are test data, 0644 is intentional.
				t.Errorf("NewRealRepo: write %s: %v", full, wErr)
				return dir, nil
			}
		}
		runGit(t, dir, nil, "add", "-A")
		env := []string{
			"GIT_AUTHOR_NAME=" + identity.Name, "GIT_AUTHOR_EMAIL=" + identity.Email,
			"GIT_COMMITTER_NAME=" + identity.Name, "GIT_COMMITTER_EMAIL=" + identity.Email,
		}
		runGit(t, dir, env, "commit", "-q", "-m", sc.Message)
	}

	repository, err := gitrepository.New(
		gitrepository.Config{
			Root:          dir,
			DefaultAuthor: gitrepository.Identity{Name: "Eden Platform", Email: "platform@eden.dev", Kind: gitrepository.ActorPlatform},
		},
		gitrepository.Deps{
			Backend: gitrepository.SystemGit(),
			Secrets: nil,
			Clock:   fixedClock{at: epoch},
		},
	)
	if err != nil {
		t.Errorf("NewRealRepo: construct repository: %v", err)
		return dir, nil
	}
	return dir, repository
}

// runGit runs a git command in dir for the seed harness, failing the test on error. It is the
// harness's own git driver (independent of the library's Backend) so the seed is established
// before the Repository under test touches the repo.
func runGit(t TestingT, dir string, env []string, args ...string) {
	t.Helper()
	command := exec.Command("git", args...) //nolint:gosec // harness args are test-literal; never user input.
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

// currentBranch reads the harness repo's current branch (empty on an unborn HEAD).
func currentBranch(t TestingT, dir string) string {
	t.Helper()
	command := exec.Command("git", "symbolic-ref", "--quiet", "--short", "HEAD")
	command.Dir = dir
	command.Env = seedEnv()
	out, err := command.Output()
	if err != nil {
		return ""
	}
	return string(trimNewline(out))
}

// trimNewline trims a single trailing newline from git output.
func trimNewline(b []byte) []byte {
	if len(b) > 0 && b[len(b)-1] == '\n' {
		b = b[:len(b)-1]
	}
	return b
}
