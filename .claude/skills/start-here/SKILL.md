---
name: start-here
description: First-time setup for a freshly cloned Concord repo. Walks the developer from `git clone` to a working dev loop (`localhost:4200` reachable).
---

# /start-here

You are guiding a developer who just cloned this repo. They want to get to a green dev loop.

## Steps

1. **Read prerequisites**: `.claude/knowledge/workflows/local-dev.md` lists OS/Docker/VS Code requirements. Confirm they're met before moving on.

2. **Submodules**: If the clone wasn't `--recursive`, run `git submodule update --init --recursive`.

3. **Identity**: set repo-local git identity per `.claude/rules/git-commits.md`:
   ```bash
   git config user.name "Mateo Segura"
   git config user.email "mateo@corekinect.com"
   ```

4. **Install git hooks** (once per clone — wires the knowledge-freshness check):
   ```bash
   .claude/hooks/install.sh
   ```
   This sets `core.hooksPath=.claude/hooks` and ensures the `commit-msg` hook is executable. Future commits that touch a tracked code path without updating the matching `.claude/knowledge/` file will be refused (escape hatch: `[no-arch-change]`). See `.claude/rules/update-knowledge-on-change.md`.

4. **Credentials**: walk `.claude/knowledge/workflows/credentials.md`. List every credential they need, point at Bitwarden (`secrets.mateosegura.com`) for the canonical store. Most can wait — for first boot they only need:
   - K8s kubeconfig (only if testing against staging; not required for local dev)
   - Bitbucket API token + SSH key (only if testing the build service)

5. **Open in devcontainer**: VS Code → Reopen in Container → pick the **base** container. First-open runs `.devcontainer/ctl.sh create` automatically (~2-3 min).

6. **Start the stack**:
   ```bash
   nx start platform        # backend (Docker Compose)
   nx serve app             # frontend dev server, separate terminal
   ```

7. **Verify**: open `http://localhost:4200` — the login page should render. With `AUTH_ENABLED=false` (default in dev), the synthetic admin signs you in.

## After the loop is green

Point the user at:

- `.claude/knowledge/architecture.md` — the system overview.
- `.claude/knowledge/workflows/local-dev.md` — daily commands.
- `/plan-feature` — when they're ready to build something.

## If a step fails

Don't paper over it. Surface the exact error, point at `.claude/knowledge/workflows/debugging.md`, and walk the troubleshooting list.
